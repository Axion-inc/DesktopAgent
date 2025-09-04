// Desktop Agent WebX - Background Script 
// Enhanced with CDP support, replacing native messaging

// Import CDP components
importScripts('cdp-manager.js', 'dom-builder.js', 'overlay-manager.js');

class WebXBackground {
  constructor() {
    this.cdpManager = new CDPManager();
    this.pluginManager = new PluginManager();
    this.securityManager = new SecurityManager();
    this.requestId = 0;
    this.requestHandlers = new Map();
    this.loadedPlugins = new Map();
    
    this.setupEventListeners();
    this.initialize();
  }

  async initialize() {
    console.log('WebX Background initializing with CDP support...');
    
    try {
      await this.cdpManager.initialize();
      await this.loadPlugins();
      console.log('WebX Background initialized successfully');
      
    } catch (error) {
      console.error('Failed to initialize WebX Background:', error);
    }
  }

  setupEventListeners() {
    // Handle messages from content scripts and external sources
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
      return true; // Keep message channel open for async responses
    });

    // Handle tab updates
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (changeInfo.status === 'complete') {
        this.onTabLoaded(tabId, tab);
      }
    });

    // Handle tab removal
    chrome.tabs.onRemoved.addListener((tabId) => {
      this.cdpManager.detachFromTab(tabId);
    });

    // Handle extension lifecycle
    chrome.runtime.onStartup.addListener(() => {
      this.initialize();
    });
    
    chrome.runtime.onInstalled.addListener(() => {
      console.log('Desktop Agent WebX CDP installed');
      this.initialize();
    });
  }

  async handleMessage(message, sender, sendResponse) {
    const { type, method, params, id } = message;
    
    try {
      let result;

      switch (type) {
        case 'cdp_call':
          result = await this.handleCDPCall(method, params, sender.tab?.id);
          break;
          
        case 'plugin_call':
          result = await this.handlePluginCall(method, params, sender);
          break;
          
        case 'build_dom_tree':
          result = await this.buildDOMTree(sender.tab?.id, params);
          break;
          
        case 'find_element':
          result = await this.findElement(sender.tab?.id, params);
          break;
          
        case 'reload_plugins':
          result = await this.loadPlugins();
          break;
          
        default:
          throw new Error(`Unknown message type: ${type}`);
      }

      sendResponse({ success: true, result, id });
      
    } catch (error) {
      console.error(`Error handling message:`, error);
      sendResponse({ 
        success: false, 
        error: error.message, 
        id 
      });
    }
  }

  async handleCDPCall(method, params, tabId) {
    // Validate security permissions
    await this.securityManager.validateOperation(method, params);

    switch (method) {
      case 'click_element':
        return await this.cdpManager.clickElement(tabId, params.selector, params);
        
      case 'fill_input':
        return await this.cdpManager.fillInput(tabId, params.selector, params.text, params);
        
      case 'take_screenshot':
        return await this.cdpManager.takeScreenshot(tabId, params);
        
      case 'upload_file':
        return await this.cdpManager.uploadFile(tabId, params.selector, params.filePath, params);
        
      case 'wait_for_element':
        return await this.cdpManager.waitForElement(tabId, params);
        
      case 'highlight_element':
        return await this.cdpManager.highlightElement(tabId, params.selector, params);
        
      case 'clear_highlights':
        return await this.cdpManager.clearHighlights(tabId);
        
      default:
        throw new Error(`Unknown CDP method: ${method}`);
    }
  }

  async buildDOMTree(tabId, options = {}) {
    if (!tabId) {
      throw new Error('Tab ID required for DOM tree building');
    }

    // Ensure CDP connection exists
    await this.cdpManager.attachToTab(tabId);
    
    // Build tree with numbered labels
    const result = await this.cdpManager.buildDOMTree(tabId, {
      addNumberedLabels: true,
      includeInvisible: false,
      includeNonInteractive: options.includeAll || false,
      maxDepth: options.maxDepth || 10
    });

    return {
      ...result,
      timestamp: Date.now(),
      tabId
    };
  }

  async findElement(tabId, params) {
    const { selector, text, role, labelId } = params;
    
    if (!tabId) {
      throw new Error('Tab ID required for element finding');
    }

    const element = await this.cdpManager.findElement(tabId, selector, {
      text, role, labelId
    });

    if (!element) {
      throw new Error('Element not found with given criteria');
    }

    return {
      found: true,
      element: {
        labelId: element.labelId,
        nodeId: element.nodeId,
        tagName: element.tagName,
        text: element.text,
        rect: element.rect,
        interactive: element.interactive
      }
    };
  }

  async loadPlugins() {
    try {
      // Get list of installed plugins from API
      const response = await fetch('http://localhost:8000/api/webx/plugins/installed');
      if (response.ok) {
        const installedPlugins = await response.json();
        
        for (const plugin of installedPlugins) {
          await this.loadPlugin(plugin.id);
        }
        
        return { success: true, loaded: installedPlugins.length };
      } else {
        console.warn('Could not fetch installed plugins list');
      }
    } catch (error) {
      console.warn('Plugin loading failed:', error);
      // Load built-in plugins as fallback
      await this.loadBuiltInPlugins();
    }
    
    return { success: true, loaded: 'builtin' };
  }

  async loadPlugin(pluginId) {
    try {
      // Get plugin files from API
      const response = await fetch(`http://localhost:8000/api/webx/plugins/${pluginId}/files`);
      if (response.ok) {
        const pluginData = await response.json();
        
        // Initialize plugin with CDP manager
        const plugin = await this.initializePlugin(pluginData, pluginId);
        if (plugin) {
          this.loadedPlugins.set(pluginId, plugin);
          console.log(`CDP-enabled plugin loaded: ${pluginId}`);
        }
      }
    } catch (error) {
      console.error(`Failed to load plugin ${pluginId}:`, error);
    }
  }

  async initializePlugin(pluginData, pluginId) {
    try {
      // Create plugin instance with CDP access
      const plugin = {
        id: pluginId,
        data: pluginData,
        cdpManager: this.cdpManager,
        initialize: async () => {
          // Plugin initialization with CDP support
          console.log(`Initializing plugin ${pluginId} with CDP support`);
          
          // Inject plugin scripts into all current tabs
          const tabs = await chrome.tabs.query({});
          for (const tab of tabs) {
            try {
              await this.injectPluginToTab(tab.id, pluginData, pluginId);
            } catch (error) {
              // Tab might not be accessible, skip silently
            }
          }
          
          return true;
        },
        activate: async (tabId) => {
          // Activate plugin for specific tab
          await this.injectPluginToTab(tabId, pluginData, pluginId);
        }
      };
      
      await plugin.initialize();
      return plugin;
      
    } catch (error) {
      console.error(`Failed to initialize plugin ${pluginId}:`, error);
      return null;
    }
  }

  async injectPluginToTab(tabId, pluginData, pluginId) {
    try {
      // Inject CDP-enabled SDK first
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['sdk/webx-plugin-cdp-sdk.js']
      });
      
      // Inject plugin files
      for (const fileContent of pluginData.files) {
        await chrome.scripting.executeScript({
          target: { tabId },
          func: this.injectPluginCode,
          args: [fileContent, pluginId]
        });
      }
      
    } catch (error) {
      console.warn(`Failed to inject plugin ${pluginId} to tab ${tabId}:`, error);
    }
  }

  injectPluginCode(code, pluginId) {
    try {
      // Create script element and execute
      const script = document.createElement('script');
      script.textContent = `
        (function() {
          console.log('Loading WebX plugin: ${pluginId}');
          ${code}
        })();
      `;
      document.head.appendChild(script);
      document.head.removeChild(script);
    } catch (error) {
      console.error(`Failed to inject plugin ${pluginId}:`, error);
    }
  }

  async loadBuiltInPlugins() {
    try {
      const tabs = await chrome.tabs.query({});
      for (const tab of tabs) {
        try {
          // Inject CDP-enabled SDK
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['sdk/webx-plugin-cdp-sdk.js']
          });
          
          // Inject built-in plugins
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['plugins/form-helper-plugin.js']
          });
        } catch (error) {
          // Tab might not be accessible, skip silently
        }
      }
      
      console.log('Built-in CDP plugins loaded');
    } catch (error) {
      console.error('Failed to load built-in plugins:', error);
    }
  }

  async handlePluginCall(method, params, sender) {
    const { pluginId, ...pluginParams } = params;
    
    const plugin = this.loadedPlugins.get(pluginId);
    if (!plugin) {
      throw new Error(`Plugin not loaded: ${pluginId}`);
    }
    
    // Execute plugin method with CDP context
    switch (method) {
      case 'activate':
        return await plugin.activate(sender.tab?.id);
        
      case 'execute':
        return await this.executePluginMethod(plugin, pluginParams, sender.tab?.id);
        
      default:
        throw new Error(`Unknown plugin method: ${method}`);
    }
  }

  async executePluginMethod(plugin, params, tabId) {
    // Provide CDP context to plugin
    const cdpContext = {
      tabId,
      cdpManager: this.cdpManager,
      buildDOMTree: () => this.buildDOMTree(tabId),
      findElement: (selector, options) => this.cdpManager.findElement(tabId, selector, options),
      clickElement: (selector, options) => this.cdpManager.clickElement(tabId, selector, options),
      fillInput: (selector, text, options) => this.cdpManager.fillInput(tabId, selector, text, options)
    };
    
    // Execute plugin with CDP context
    return await plugin.execute(params, cdpContext);
  }

  async onTabLoaded(tabId, tab) {
    try {
      // Auto-attach to new tabs and rebuild DOM tree
      await this.cdpManager.attachToTab(tabId);
      
      // Inject plugins into new tab
      for (const [pluginId, plugin] of this.loadedPlugins) {
        try {
          await plugin.activate(tabId);
        } catch (error) {
          console.warn(`Failed to activate plugin ${pluginId} in tab ${tabId}:`, error);
        }
      }
      
      // Notify content scripts that background is ready
      chrome.tabs.sendMessage(tabId, {
        type: 'webx_ready',
        cdpEnabled: true
      }).catch(() => {
        // Tab might not have content script yet
      });
      
    } catch (error) {
      console.warn(`Failed to setup tab ${tabId}:`, error);
    }
  }

  async cleanup() {
    console.log('Cleaning up WebX Background...');
    
    // Cleanup CDP manager
    if (this.cdpManager) {
      await this.cdpManager.cleanup();
    }
    
    // Cleanup loaded plugins
    for (const [pluginId, plugin] of this.loadedPlugins) {
      try {
        if (plugin.cleanup) {
          await plugin.cleanup();
        }
      } catch (error) {
        console.warn(`Failed to cleanup plugin ${pluginId}:`, error);
      }
    }
    
    this.loadedPlugins.clear();
    console.log('WebX Background cleanup complete');
  }
}

// Security Manager for validating operations
class SecurityManager {
  constructor() {
    this.allowedOperations = new Set([
      'click_element', 'fill_input', 'take_screenshot', 'upload_file',
      'wait_for_element', 'highlight_element', 'clear_highlights'
    ]);
  }
  
  async validateOperation(method, params) {
    if (!this.allowedOperations.has(method)) {
      throw new Error(`Operation not allowed: ${method}`);
    }
    
    // Add additional security validations as needed
    return true;
  }
}

// Plugin Manager for handling plugin lifecycle
class PluginManager {
  constructor() {
    this.installedPlugins = new Map();
  }
  
  async initialize() {
    console.log('Plugin Manager initialized');
  }
}

// Overlay Manager for visual feedback
class OverlayManager {
  constructor() {
    this.overlays = new Map();
  }
  
  async createOverlay(tabId, element, options = {}) {
    // Implementation for creating visual overlays
    console.log(`Creating overlay for tab ${tabId}`);
  }
  
  async removeOverlay(tabId, overlayId) {
    // Implementation for removing visual overlays
    console.log(`Removing overlay ${overlayId} from tab ${tabId}`);
  }
}

// Initialize background script
const webxBackground = new WebXBackground();

// Cleanup on extension unload
chrome.runtime.onSuspend.addListener(() => {
  webxBackground.cleanup();
});

// Handle service worker lifecycle
self.addEventListener('beforeunload', () => {
  webxBackground.cleanup();
});