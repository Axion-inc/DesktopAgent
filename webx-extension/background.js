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
      // Optional: connect to local WebSocket bridge for host coordination
      this.connectWebSocketBridge();
      // Optional: connect to native messaging host bridge
      this.connectNativeBridge();
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
        
        case 'exec_batch':
          result = await this.executeBatch(params, sender.tab?.id);
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

  async executeBatch(params, senderTabId) {
    const { guards = {}, actions = [], evidence = {}, context = 'default' } = params || {};
    // Minimal validation for required shapes
    if (!Array.isArray(actions) || actions.length === 0) throw new Error('actions array is required');
    for (const a of actions) {
      if (!a || typeof a.type !== 'string') throw new Error('each action requires a type');
    }
    const { allowHosts = [], maxRetriesPerStep = 0 } = guards;

    // Determine target tab: prefer sender tab; fallback to active tab
    const tabId = await this.resolveTargetTabId(senderTabId);
    if (!tabId) throw new Error('No target tab available');

    // Host guard check (if allowHosts specified)
    if (allowHosts.length > 0) {
      const info = await this.callContentRPC(tabId, 'get_page_info', {});
      try {
        const url = new URL(info.url);
        if (!allowHosts.some(h => url.hostname.endsWith(h))) {
          throw new Error(`Host not allowed: ${url.hostname}`);
        }
      } catch (e) {
        throw new Error(`Invalid page URL for host guard: ${(e && e.message) || e}`);
      }
    }

    const results = [];
    const state = { currentFrame: null, pierceShadow: true };
    for (const _action of actions) {
      const action = { ..._action };

      // Stateful directives
      if (action.type === 'frame_select') {
        const frame = action.frame || (typeof action.index !== 'undefined' ? { index: action.index } : null);
        if (!frame) throw new Error('frame_select requires frame selector or index');
        state.currentFrame = frame;
        results.push({ id: action.id, type: action.type, status: 'success', frame });
        continue;
      }
      if (action.type === 'frame_clear') {
        state.currentFrame = null;
        results.push({ id: action.id, type: action.type, status: 'success' });
        continue;
      }
      if (action.type === 'pierce_shadow') {
        state.pierceShadow = true;
        results.push({ id: action.id, type: action.type, status: 'success' });
        continue;
      }

      // Default frame propagation
      if (state.currentFrame && typeof action.frame === 'undefined') {
        action.frame = state.currentFrame;
      }
      let attempt = 0;
      let stepResult;
      while (true) {
        try {
          stepResult = await this.executeSingleAction(tabId, action);
          break;
        } catch (err) {
          if (attempt < maxRetriesPerStep) {
            attempt += 1;
            await this.sleep(200 + 200 * attempt);
            continue;
          }
          stepResult = { status: 'error', error: err?.message || String(err) };
          break;
        }
      }

      // Evidence capture
      if (evidence && evidence.screenshotEach === true) {
        try {
          const shot = await this.cdpManager.takeScreenshot(tabId, { format: 'png' });
          stepResult.evidence = stepResult.evidence || {};
          stepResult.evidence.screenshot = shot?.dataUrl || shot;
        } catch (e) {
          // Non-fatal
        }
      }
      if (evidence && evidence.domSchemaEach === true) {
        try {
          const schema = await this.callContentRPC(tabId, 'get_dom_schema', {});
          stepResult.evidence = stepResult.evidence || {};
          stepResult.evidence.domSchema = schema?.schema || schema;
        } catch (e) {
          // Non-fatal
        }
      }

      results.push({ id: action.id, type: action.type, ...stepResult });
    }

    return {
      context,
      steps: results,
      finishedAt: Date.now()
    };
  }

  async executeSingleAction(tabId, action) {
    const type = action?.type;
    switch (type) {
      case 'goto': {
        const url = action.url;
        if (!url) throw new Error('goto requires url');
        await this.navigateTab(tabId, url);
        return { status: 'success', url };
      }
      case 'fill_by_label': {
        const { label, text, selector, frame } = action;
        if (!label && !selector) throw new Error('fill_by_label requires label or selector');
        let res;
        try {
          res = await this.callContentRPC(tabId, 'fill_input', { label, selector, text, frame });
        } catch (e) {
          // Fallback: CDP fill
          res = await this.cdpManager.fillInput(tabId, selector || null, { text, label });
        }
        return { status: 'success', result: res };
      }
      case 'click_by_text': {
        const { text, role, selector, frame } = action;
        if (!text && !selector) throw new Error('click_by_text requires text or selector');
        let res;
        try {
          res = await this.callContentRPC(tabId, 'click_element', { text, role, selector, frame });
        } catch (e) {
          // Fallback: try CDP click (by selector or text/role)
          res = await this.cdpManager.clickElement(tabId, selector || null, { text, role });
        }
        return { status: 'success', result: res };
      }
      case 'wait_for_text': {
        const { contains, role, timeoutMs = 8000, frame } = action;
        if (!contains) throw new Error('wait_for_text requires contains');
        const res = await this.callContentRPC(tabId, 'wait_for_element', { text: contains, role, timeout: timeoutMs, frame });
        if (!res?.found) throw new Error('Text not found');
        return { status: 'success', result: res };
      }
      case 'download_file': {
        const { url, filename } = action;
        if (!url) throw new Error('download_file requires url');
        const id = await chrome.downloads.download({ url, filename });
        return { status: 'success', downloadId: id };
      }
      case 'wait_for_download': {
        const { url, filename, timeoutMs = 30000 } = action;
        const item = await this.waitForDownloadComplete({ url, filename, timeoutMs });
        if (!item) throw new Error('Download not completed within timeout');
        return { status: 'success', item };
      }
      case 'assert_file_exists': {
        const { url, filename } = action;
        const item = await this.findDownloadItem({ url, filename });
        if (!item || item.state !== 'complete') {
          throw new Error(`Downloaded file not found or incomplete: ${filename || url || ''}`);
        }
        return { status: 'success', item };
      }
      case 'precise_click': {
        const { x, y } = action;
        if (typeof x !== 'number' || typeof y !== 'number') throw new Error('precise_click requires numeric x,y');
        const res = await this.cdpManager.clickByCoordinates(tabId, x, y);
        return { status: 'success', result: res };
      }
      case 'insert_text': {
        const { text } = action;
        if (typeof text !== 'string') throw new Error('insert_text requires text');
        const res = await this.cdpManager.insertText(tabId, text);
        return { status: 'success', result: res };
      }
      case 'get_cookie': {
        const { name, url, domain, path = '/' } = action;
        if (!name) throw new Error('get_cookie requires name');
        const details = url ? { url, name } : { url: await this.currentTabUrl(tabId), name };
        // Domain/path variants if needed
        const cookie = await chrome.cookies.get(details).catch(() => null);
        return { status: cookie ? 'success' : 'not_found', cookie };
      }
      case 'set_cookie': {
        const { name, value, url, domain, path = '/', expirationDate } = action;
        if (!name || typeof value === 'undefined') throw new Error('set_cookie requires name and value');
        const targetUrl = url || await this.currentTabUrl(tabId);
        const cookie = await chrome.cookies.set({ url: targetUrl, name, value: String(value), path, expirationDate }).catch((e)=>{ throw new Error(e?.message || 'cookie set failed'); });
        return { status: 'success', cookie };
      }
      case 'get_storage': {
        const { key } = action;
        const data = await chrome.storage.local.get(key ? [key] : null);
        return { status: 'success', data };
      }
      case 'set_storage': {
        const { key, value } = action;
        if (!key) throw new Error('set_storage requires key');
        await chrome.storage.local.set({ [key]: value });
        return { status: 'success' };
      }
      case 'set_file_input_files': {
        const { selector, files } = action;
        if (!selector || !files) throw new Error('set_file_input_files requires selector and files');
        const res = await this.cdpManager.uploadFile(tabId, selector, files);
        return { status: 'success', result: res };
      }
      default:
        throw new Error(`Unsupported action type: ${type}`);
    }
  }

  async callContentRPC(tabId, method, params) {
    return new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(tabId, { type: 'execute_rpc', method, params }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response) {
          reject(new Error('No response from content script'));
          return;
        }
        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response.result);
        }
      });
    });
  }

  async navigateTab(tabId, url) {
    await chrome.tabs.update(tabId, { url });
    // Wait for complete
    await this.waitForTabComplete(tabId, 20000);
  }

  async resolveTargetTabId(senderTabId) {
    if (senderTabId) return senderTabId;
    const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
    return active?.id || null;
  }

  async waitForTabComplete(tabId, timeoutMs = 20000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const listener = (updatedTabId, changeInfo) => {
        if (updatedTabId === tabId && changeInfo.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve(true);
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      const timer = setInterval(() => {
        if (Date.now() - start > timeoutMs) {
          try { chrome.tabs.onUpdated.removeListener(listener); } catch (e) {}
          clearInterval(timer);
          reject(new Error('Navigation timeout'));
        }
      }, 500);
    });
  }

  sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  async currentTabUrl(tabId) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    try {
      const info = await this.callContentRPC(tabId, 'get_page_info', {});
      return info?.url || tab?.url || '';
    } catch (_) {
      return tab?.url || '';
    }
  }

  async findDownloadItem({ url, filename }) {
    const query = {};
    if (url) query.urlRegex = this.escapeRegex(url);
    const items = await chrome.downloads.search(query);
    if (filename) {
      const matched = items.find(i => (i.filename || '').toLowerCase().includes(String(filename).toLowerCase()));
      return matched || null;
    }
    return items[0] || null;
  }

  async waitForDownloadComplete({ url, filename, timeoutMs = 30000 }) {
    const start = Date.now();
    // First, try current items
    const existing = await this.findDownloadItem({ url, filename });
    if (existing && existing.state === 'complete') return existing;

    return new Promise((resolve, reject) => {
      const onChanged = async (delta) => {
        try {
          if (!delta || !delta.id) return;
          const items = await chrome.downloads.search({ id: delta.id });
          const item = items && items[0];
          if (!item) return;
          const nameMatch = filename ? (item.filename || '').toLowerCase().includes(String(filename).toLowerCase()) : true;
          const urlMatch = url ? String(item.url || '').includes(url) : true;
          if (nameMatch && urlMatch && item.state === 'complete') {
            cleanup();
            resolve(item);
          }
        } catch (e) {
          // ignore
        }
      };
      const timer = setInterval(async () => {
        if (Date.now() - start > timeoutMs) {
          cleanup();
          resolve(null);
        }
      }, 500);
      const cleanup = () => {
        try { chrome.downloads.onChanged.removeListener(onChanged); } catch (_) {}
        clearInterval(timer);
      };
      chrome.downloads.onChanged.addListener(onChanged);
    });
  }

  escapeRegex(s) {
    try { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); } catch (_) { return s; }
  }

  // --- WebSocket bridge to DesktopAgent host (optional) ---
  connectWebSocketBridge() {
    const url = (self.WEBX_WS_URL || 'ws://127.0.0.1:8765');
    let ws;
    const connect = () => {
      try {
        ws = new WebSocket(url);
      } catch (e) {
        setTimeout(connect, 1500);
        return;
      }
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'hello', role: 'extension' }));
      };
      ws.onmessage = async (event) => {
        try {
          const msg = JSON.parse(event.data || '{}');
          if (msg && msg.id && msg.method) {
            let payload;
            if (msg.method === 'webx.exec_batch') {
              payload = await this.executeBatch(msg.params || {}, null);
            } else if (msg.method === 'webx.ping') {
              payload = { pong: Date.now() };
            } else {
              payload = { error: `Unknown method: ${msg.method}` };
            }
            ws.send(JSON.stringify({ id: msg.id, result: payload }));
          }
        } catch (e) {
          try { ws.send(JSON.stringify({ error: String(e?.message || e) })); } catch (_) {}
        }
      };
      ws.onclose = () => {
        setTimeout(connect, 1500);
      };
      ws.onerror = () => {
        try { ws.close(); } catch (e) {}
      };
    };
    connect();
  }

  // --- Native messaging bridge (optional) ---
  connectNativeBridge() {
    let port = null;
    try {
      port = chrome.runtime.connectNative('com.desktopagent.webx');
    } catch (e) {
      console.warn('Native host connect failed:', e?.message || e);
      return;
    }
    if (!port) return;

    port.onMessage.addListener(async (msg) => {
      try {
        if (msg && msg.id && msg.method) {
          let payload;
          if (msg.method === 'webx.exec_batch') {
            payload = await this.executeBatch(msg.params || {}, null);
          } else if (msg.method === 'webx.ping') {
            payload = { pong: Date.now() };
          } else {
            payload = { error: `Unknown method: ${msg.method}` };
          }
          port.postMessage({ id: msg.id, result: payload });
        }
      } catch (e) {
        try { port.postMessage({ error: String(e?.message || e) }); } catch (_) {}
      }
    });

    port.onDisconnect.addListener(() => {
      // Attempt periodic reconnect
      setTimeout(() => this.connectNativeBridge(), 2000);
    });
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
