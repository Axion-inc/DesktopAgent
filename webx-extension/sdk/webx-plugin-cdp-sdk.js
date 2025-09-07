/**
 * WebX Plugin SDK v2.0 - CDP Edition
 * Enhanced plugin SDK with direct Chrome DevTools Protocol access
 * 
 * This SDK provides plugins with direct access to CDP functionality
 * while maintaining security through capability-based permissions.
 */

// First, load the base SDK
if (typeof WebXPluginSDK === 'undefined') {
  // Load base SDK if not already loaded
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('sdk/webx-plugin-sdk.js');
  script.onload = () => {
    console.log('Base WebX Plugin SDK loaded');
  };
  document.head.appendChild(script);
}

/**
 * Enhanced WebX Plugin SDK with CDP support
 */
class WebXPluginCDPSDK extends WebXPluginSDK {
  constructor() {
    super();
    this.cdpManager = null;
    this.domBuilder = null;
    this.overlayManager = null;
    this.currentTabId = null;
  }

  async initialize(cdpManager = null) {
    await super.initialize();
    
    // Get CDP manager from background script or use provided one
    if (cdpManager) {
      this.cdpManager = cdpManager;
    } else {
      // Request CDP manager from background script
      try {
        const response = await chrome.runtime.sendMessage({
          type: 'get_cdp_manager'
        });
        if (response && response.success) {
          this.cdpManager = response.cdpManager;
        }
      } catch (error) {
        console.warn('Could not get CDP manager from background:', error);
      }
    }
    
    // Get current tab ID
    this.currentTabId = await this.getCurrentTabId();
    
    // Setup enhanced API methods with CDP support
    this.setupCDPMethods();
    
    console.log('WebX Plugin CDP SDK initialized');
  }

  setupCDPMethods() {
    // Override parent methods with CDP implementations
    this.findElement = this.findElementCDP.bind(this);
    this.clickElement = this.clickElementCDP.bind(this);
    this.fillForm = this.fillFormCDP.bind(this);
    this.takeScreenshot = this.takeScreenshotCDP.bind(this);
    this.buildDOMTree = this.buildDOMTreeCDP.bind(this);
    
    // Add CDP-specific methods
    this.highlightElement = this.highlightElementCDP.bind(this);
    this.clearHighlights = this.clearHighlightsCDP.bind(this);
    this.waitForElement = this.waitForElementCDP.bind(this);
    this.uploadFile = this.uploadFileCDP.bind(this);
    this.showProgress = this.showProgressCDP.bind(this);
  }

  // CDP-enhanced core methods
  async findElementCDP(selector, options = {}) {
    this.requireCapability(WebXCapabilities.DOM_READ);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'find_element',
        params: {
          selector,
          text: options.text,
          role: options.role,
          labelId: options.labelId
        }
      });
      
      if (response && response.success) {
        return response.result.element;
      } else {
        throw new Error(response?.error || 'Element not found');
      }
    } catch (error) {
      console.error('findElementCDP failed:', error);
      throw error;
    }
  }

  async clickElementCDP(selector, options = {}) {
    this.requireCapability(WebXCapabilities.CLICK_ELEMENTS);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'click_element',
        params: {
          selector,
          text: options.text,
          role: options.role,
          labelId: options.labelId,
          clickOptions: options
        }
      });
      
      if (response && response.success) {
        // Show visual feedback
        if (options.showFeedback !== false) {
          await this.showClickFeedback(response.result);
        }
        return response.result;
      } else {
        throw new Error(response?.error || 'Click failed');
      }
    } catch (error) {
      console.error('clickElementCDP failed:', error);
      throw error;
    }
  }

  async fillFormCDP(fields, options = {}) {
    this.requireCapability(WebXCapabilities.FORM_FILL);
    
    const results = [];
    
    for (const [selector, value] of Object.entries(fields)) {
      try {
        const response = await chrome.runtime.sendMessage({
          type: 'cdp_call',
          method: 'fill_input',
          params: {
            selector,
            text: value,
            fillOptions: options
          }
        });
        
        if (response && response.success) {
          // Show visual feedback
          if (options.showFeedback !== false) {
            await this.showFillFeedback(response.result, value);
          }
          results.push({ selector, success: true, result: response.result });
        } else {
          results.push({ selector, success: false, error: response?.error || 'Fill failed' });
        }
      } catch (error) {
        console.error(`fillFormCDP failed for ${selector}:`, error);
        results.push({ selector, success: false, error: error.message });
      }
    }
    
    return results;
  }

  async takeScreenshotCDP(options = {}) {
    this.requireCapability(WebXCapabilities.SCREENSHOT);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'take_screenshot',
        params: {
          format: options.format || 'png',
          quality: options.quality || 90,
          fullPage: options.fullPage || false
        }
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'Screenshot failed');
      }
    } catch (error) {
      console.error('takeScreenshotCDP failed:', error);
      throw error;
    }
  }

  async buildDOMTreeCDP(options = {}) {
    this.requireCapability(WebXCapabilities.DOM_READ);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'build_dom_tree',
        params: {
          includeInvisible: options.includeInvisible || false,
          includeAll: options.includeAll || false,
          maxDepth: options.maxDepth || 10
        }
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'DOM tree building failed');
      }
    } catch (error) {
      console.error('buildDOMTreeCDP failed:', error);
      throw error;
    }
  }

  // CDP-specific new capabilities
  async highlightElementCDP(selector, options = {}) {
    this.requireCapability(WebXCapabilities.DOM_READ);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'highlight_element',
        params: {
          selector,
          text: options.text,
          role: options.role,
          labelId: options.labelId,
          color: options.color || '#FF6B6B',
          duration: options.duration
        }
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'Highlight failed');
      }
    } catch (error) {
      console.error('highlightElementCDP failed:', error);
      throw error;
    }
  }

  async clearHighlightsCDP() {
    this.requireCapability(WebXCapabilities.DOM_READ);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'clear_highlights'
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'Clear highlights failed');
      }
    } catch (error) {
      console.error('clearHighlightsCDP failed:', error);
      throw error;
    }
  }

  async waitForElementCDP(selector, options = {}) {
    this.requireCapability(WebXCapabilities.DOM_READ);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'wait_for_element',
        params: {
          selector,
          text: options.text,
          role: options.role,
          timeout: options.timeout || 10000,
          visible: options.visible !== false
        }
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'Wait for element failed');
      }
    } catch (error) {
      console.error('waitForElementCDP failed:', error);
      throw error;
    }
  }

  async uploadFileCDP(filePath, selector = null, options = {}) {
    this.requireCapability(WebXCapabilities.FILE_UPLOAD);
    
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'cdp_call',
        method: 'upload_file',
        params: {
          filePath,
          selector,
          label: options.label,
          uploadOptions: options
        }
      });
      
      if (response && response.success) {
        return response.result;
      } else {
        throw new Error(response?.error || 'File upload failed');
      }
    } catch (error) {
      console.error('uploadFileCDP failed:', error);
      throw error;
    }
  }

  async showProgressCDP(message, options = {}) {
    try {
      // Show progress overlay using background script
      const response = await chrome.runtime.sendMessage({
        type: 'show_progress',
        params: {
          message,
          position: options.position || 'top-right',
          duration: options.duration || 3000,
          type: options.type || 'info'
        }
      });
      
      if (response && response.success) {
        return response.result;
      }
    } catch (error) {
      console.warn('showProgressCDP failed:', error);
      // Fallback to console
      console.info(`[${options.type || 'INFO'}] ${message}`);
    }
  }

  // Visual feedback methods
  async showClickFeedback(elementData) {
    if (!elementData || !elementData.rect) return;
    
    try {
      // Create click ripple effect
      const overlay = document.createElement('div');
      overlay.style.cssText = `
        position: absolute !important;
        left: ${elementData.rect.x + elementData.rect.width / 2 - 10}px !important;
        top: ${elementData.rect.y + elementData.rect.height / 2 - 10}px !important;
        width: 20px !important;
        height: 20px !important;
        background: #4CAF50 !important;
        border-radius: 50% !important;
        pointer-events: none !important;
        z-index: 999999 !important;
        animation: webx-click-ripple 0.6s ease-out !important;
        opacity: 0.8 !important;
      `;
      
      // Add animation styles if not present
      if (!document.getElementById('webx-click-styles')) {
        const style = document.createElement('style');
        style.id = 'webx-click-styles';
        style.textContent = `
          @keyframes webx-click-ripple {
            0% { transform: scale(0.5); opacity: 0.8; }
            100% { transform: scale(3); opacity: 0; }
          }
        `;
        document.head.appendChild(style);
      }
      
      document.body.appendChild(overlay);
      setTimeout(() => overlay.remove(), 600);
      
    } catch (error) {
      console.warn('Click feedback failed:', error);
    }
  }

  async showFillFeedback(elementData, text) {
    if (!elementData || !elementData.rect) return;
    
    try {
      // Create fill success indicator
      const overlay = document.createElement('div');
      overlay.textContent = '✓';
      overlay.style.cssText = `
        position: absolute !important;
        left: ${elementData.rect.x + elementData.rect.width - 25}px !important;
        top: ${elementData.rect.y - 5}px !important;
        background: #4CAF50 !important;
        color: white !important;
        width: 20px !important;
        height: 20px !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 12px !important;
        font-weight: bold !important;
        pointer-events: none !important;
        z-index: 999999 !important;
        opacity: 0 !important;
        transform: scale(0.5) !important;
        transition: all 0.3s ease !important;
      `;
      
      document.body.appendChild(overlay);
      
      // Animate in
      requestAnimationFrame(() => {
        overlay.style.opacity = '1';
        overlay.style.transform = 'scale(1)';
      });
      
      // Remove after delay
      setTimeout(() => {
        overlay.style.opacity = '0';
        overlay.style.transform = 'scale(0.5)';
        setTimeout(() => overlay.remove(), 300);
      }, 1500);
      
    } catch (error) {
      console.warn('Fill feedback failed:', error);
    }
  }

  // Utility methods
  async getCurrentTabId() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      return tabs[0]?.id || null;
    } catch (error) {
      console.warn('Could not get current tab ID:', error);
      return null;
    }
  }

  async getElementByLabel(labelId) {
    return await this.findElementCDP(null, { labelId: parseInt(labelId) });
  }

  async getElementStats() {
    try {
      const domTree = await this.buildDOMTreeCDP();
      return {
        totalElements: domTree.labelCount || 0,
        timestamp: domTree.timestamp
      };
    } catch (error) {
      console.warn('Could not get element stats:', error);
      return { totalElements: 0, timestamp: Date.now() };
    }
  }

  // Plugin lifecycle with CDP support
  async activateWithCDP(tabId = null) {
    const targetTabId = tabId || this.currentTabId;
    
    if (this.cdpManager && targetTabId) {
      try {
        // Ensure CDP connection to tab
        await this.cdpManager.attachToTab(targetTabId);
        console.log(`Plugin activated with CDP for tab ${targetTabId}`);
        return true;
      } catch (error) {
        console.warn('CDP activation failed:', error);
        return false;
      }
    }
    
    return false;
  }

  async deactivateFromCDP(tabId = null) {
    const targetTabId = tabId || this.currentTabId;
    
    if (this.cdpManager && targetTabId) {
      try {
        // Clear any highlights or overlays
        await this.clearHighlightsCDP();
        console.log(`Plugin deactivated from CDP for tab ${targetTabId}`);
        return true;
      } catch (error) {
        console.warn('CDP deactivation failed:', error);
        return false;
      }
    }
    
    return false;
  }

  // Enhanced capability requirements for CDP features
  static get CDPCapabilities() {
    return {
      ...WebXCapabilities,
      ELEMENT_HIGHLIGHT: 'element_highlight',
      WAIT_FOR_ELEMENT: 'wait_for_element',
      PROGRESS_OVERLAY: 'progress_overlay',
      VISUAL_FEEDBACK: 'visual_feedback'
    };
  }
}

// Export enhanced SDK
if (typeof window !== 'undefined') {
  window.WebXPluginCDPSDK = WebXPluginCDPSDK;
  
  // Make CDP capabilities available
  window.WebXCDPCapabilities = WebXPluginCDPSDK.CDPCapabilities;
  
  console.log('WebX Plugin CDP SDK loaded');
}

// Auto-initialize if base SDK is already loaded
if (typeof WebXPluginSDK !== 'undefined') {
  console.log('WebX Plugin CDP SDK ready');
} else {
  // Wait for base SDK to load
  const checkBaseSDK = setInterval(() => {
    if (typeof WebXPluginSDK !== 'undefined') {
      clearInterval(checkBaseSDK);
      console.log('WebX Plugin CDP SDK ready (after base SDK load)');
    }
  }, 100);
  
  // Timeout after 5 seconds
  setTimeout(() => {
    clearInterval(checkBaseSDK);
    console.warn('Base WebX Plugin SDK not loaded within timeout');
  }, 5000);
}