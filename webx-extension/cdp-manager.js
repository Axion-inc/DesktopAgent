/**
 * CDP Manager - Core Chrome DevTools Protocol handler
 * Replaces native messaging host with direct CDP communication
 * 
 * This module handles direct communication with Chrome DevTools Protocol
 * to perform browser automation without requiring native messaging.
 */

class CDPManager {
  constructor() {
    this.connections = new Map(); // tabId -> CDP connection
    this.domBuilders = new Map(); // tabId -> DOMBuilder instance
    this.nextLabelId = 1;
    this.initialized = false;
    this.overlayManager = null;
  }

  async initialize() {
    if (this.initialized) return;
    
    try {
      console.log('Initializing CDP Manager...');
      
      // Initialize overlay manager for visual feedback
      this.overlayManager = new OverlayManager();
      
      this.initialized = true;
      console.log('CDP Manager initialized successfully');
      
    } catch (error) {
      console.error('Failed to initialize CDP Manager:', error);
      throw error;
    }
  }

  async attachToTab(tabId) {
    if (this.connections.has(tabId)) {
      return this.connections.get(tabId);
    }

    try {
      console.log(`Attaching CDP to tab ${tabId}...`);
      
      // Attach debugger to tab
      await chrome.debugger.attach({ tabId }, "1.3");
      
      // Create connection object
      const connection = {
        tabId,
        attached: true,
        debuggerAPI: chrome.debugger,
        domains: new Set()
      };

      this.connections.set(tabId, connection);

      // Initialize CDP domains
      await this.initializeCDPDomains(connection);

      // Create DOM builder for this tab
      const domBuilder = new DOMBuilder(connection);
      await domBuilder.initialize();
      this.domBuilders.set(tabId, domBuilder);

      console.log(`Successfully attached to tab ${tabId}`);
      return connection;
      
    } catch (error) {
      console.error(`Failed to attach to tab ${tabId}:`, error);
      throw new Error(`CDP attachment failed: ${error.message}`);
    }
  }

  async detachFromTab(tabId) {
    try {
      const connection = this.connections.get(tabId);
      if (connection && connection.attached) {
        await chrome.debugger.detach({ tabId });
      }
      
      this.connections.delete(tabId);
      this.domBuilders.delete(tabId);
      
      console.log(`Detached from tab ${tabId}`);
      
    } catch (error) {
      console.warn(`Failed to detach from tab ${tabId}:`, error);
    }
  }

  async initializeCDPDomains(connection) {
    const { tabId } = connection;
    
    try {
      // Enable required CDP domains
      await this.sendCommand(tabId, 'DOM.enable');
      await this.sendCommand(tabId, 'Runtime.enable');
      await this.sendCommand(tabId, 'Overlay.enable');
      await this.sendCommand(tabId, 'Page.enable');
      
      connection.domains.add('DOM');
      connection.domains.add('Runtime');
      connection.domains.add('Overlay');
      connection.domains.add('Page');

      console.log(`Initialized CDP domains for tab ${tabId}`);
      
    } catch (error) {
      console.error(`Failed to initialize CDP domains for tab ${tabId}:`, error);
      throw error;
    }
  }

  async sendCommand(tabId, command, params = {}) {
    return new Promise((resolve, reject) => {
      chrome.debugger.sendCommand({ tabId }, command, params, (result) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(result);
        }
      });
    });
  }

  // Core CDP operations
  async clickElement(tabId, selector, options = {}) {
    try {
      const connection = await this.attachToTab(tabId);
      const element = await this.findElement(tabId, selector, options);
      
      if (!element) {
        throw new Error(`Element not found: ${JSON.stringify({ selector, ...options })}`);
      }

      // Get the element's object ID for interaction
      const objectResult = await this.sendCommand(tabId, 'DOM.resolveNode', {
        nodeId: element.nodeId
      });

      if (!objectResult || !objectResult.object) {
        throw new Error('Failed to resolve element object');
      }

      // Scroll element into view and click
      await this.sendCommand(tabId, 'Runtime.callFunctionOn', {
        functionDeclaration: `
          function() {
            this.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return new Promise(resolve => {
              setTimeout(() => {
                this.focus();
                this.click();
                resolve({ clicked: true, tagName: this.tagName });
              }, 100);
            });
          }
        `,
        objectId: objectResult.object.objectId,
        awaitPromise: true
      });

      console.log(`Clicked element with label ${element.labelId}`);
      
      return { 
        success: true, 
        elementId: element.nodeId,
        labelId: element.labelId,
        action: 'click'
      };
      
    } catch (error) {
      console.error(`Failed to click element:`, error);
      throw error;
    }
  }

  async fillInput(tabId, selector, text, options = {}) {
    try {
      const connection = await this.attachToTab(tabId);
      const element = await this.findElement(tabId, selector, options);
      
      if (!element) {
        throw new Error(`Element not found: ${JSON.stringify({ selector, ...options })}`);
      }

      // Get the element's object ID for interaction
      const objectResult = await this.sendCommand(tabId, 'DOM.resolveNode', {
        nodeId: element.nodeId
      });

      if (!objectResult || !objectResult.object) {
        throw new Error('Failed to resolve element object');
      }

      // Fill the input with proper event handling
      await this.sendCommand(tabId, 'Runtime.callFunctionOn', {
        functionDeclaration: `
          function(text) {
            this.focus();
            this.select();
            this.value = text;
            
            // Trigger input events for modern frameworks
            this.dispatchEvent(new Event('input', { bubbles: true }));
            this.dispatchEvent(new Event('change', { bubbles: true }));
            this.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
            
            return { 
              filled: true, 
              value: this.value, 
              tagName: this.tagName 
            };
          }
        `,
        arguments: [{ value: text }],
        objectId: objectResult.object.objectId
      });

      console.log(`Filled element with label ${element.labelId}: "${text}"`);
      
      return { 
        success: true, 
        elementId: element.nodeId,
        labelId: element.labelId,
        text: text,
        action: 'fill'
      };
      
    } catch (error) {
      console.error(`Failed to fill element:`, error);
      throw error;
    }
  }

  async takeScreenshot(tabId, options = {}) {
    try {
      const {
        format = 'png',
        quality = 90,
        fullPage = false,
        clip = null
      } = options;

      await this.attachToTab(tabId);
      
      const screenshotParams = { format };
      
      if (format === 'jpeg') {
        screenshotParams.quality = quality;
      }
      
      if (clip) {
        screenshotParams.clip = clip;
      }

      // Take screenshot using Page domain
      const result = await this.sendCommand(tabId, 'Page.captureScreenshot', screenshotParams);
      
      if (!result || !result.data) {
        throw new Error('Failed to capture screenshot');
      }

      // Convert to data URL
      const dataUrl = `data:image/${format};base64,${result.data}`;
      
      console.log(`Captured screenshot for tab ${tabId}`);
      
      return { 
        success: true, 
        dataUrl, 
        format,
        fullPage,
        timestamp: Date.now()
      };
      
    } catch (error) {
      console.error(`Failed to take screenshot:`, error);
      throw error;
    }
  }

  async uploadFile(tabId, selector, filePath, options = {}) {
    try {
      const connection = await this.attachToTab(tabId);
      const element = await this.findElement(tabId, selector, { 
        ...options,
        tagName: 'input',
        inputType: 'file'
      });
      
      if (!element) {
        throw new Error(`File input element not found: ${JSON.stringify({ selector, ...options })}`);
      }

      // Use CDP to set file input files
      await this.sendCommand(tabId, 'DOM.setFileInputFiles', {
        nodeId: element.nodeId,
        files: Array.isArray(filePath) ? filePath : [filePath]
      });

      console.log(`Uploaded file(s) to element with label ${element.labelId}`);
      
      return { 
        success: true, 
        elementId: element.nodeId,
        labelId: element.labelId,
        files: Array.isArray(filePath) ? filePath : [filePath],
        action: 'upload'
      };
      
    } catch (error) {
      console.error(`Failed to upload file:`, error);
      throw error;
    }
  }

  async waitForElement(tabId, selector, options = {}) {
    const {
      timeout = 10000,
      visible = true,
      text,
      role
    } = options;
    
    const startTime = Date.now();
    const pollInterval = 500;
    
    while (Date.now() - startTime < timeout) {
      try {
        const element = await this.findElement(tabId, selector, { text, role });
        
        if (element) {
          if (!visible || element.visible) {
            return { 
              found: true, 
              element: {
                labelId: element.labelId,
                nodeId: element.nodeId,
                tagName: element.tagName,
                text: element.text,
                visible: element.visible
              }
            };
          }
        }
        
      } catch (e) {
        // Continue waiting
      }
      
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    return { 
      found: false, 
      timeout: true, 
      duration: Date.now() - startTime 
    };
  }

  async findElement(tabId, selector, options = {}) {
    const domBuilder = this.domBuilders.get(tabId);
    if (!domBuilder) {
      throw new Error(`No DOM builder for tab ${tabId}`);
    }

    return await domBuilder.findElement(selector, options);
  }

  async buildDOMTree(tabId, options = {}) {
    const domBuilder = this.domBuilders.get(tabId);
    if (!domBuilder) {
      throw new Error(`No DOM builder for tab ${tabId}`);
    }

    return await domBuilder.buildTree(options);
  }

  async highlightElement(tabId, selector, options = {}) {
    try {
      const element = await this.findElement(tabId, selector, options);
      if (!element) {
        throw new Error(`Element not found for highlighting: ${selector}`);
      }

      await this.sendCommand(tabId, 'Overlay.highlightNode', {
        nodeId: element.nodeId,
        highlightConfig: {
          showInfo: true,
          showRulers: false,
          showExtensionLines: false,
          contentColor: { r: 255, g: 107, b: 107, a: 0.3 },
          borderColor: { r: 255, g: 82, b: 82, a: 1 }
        }
      });

      return { 
        highlighted: true, 
        elementId: element.nodeId,
        labelId: element.labelId
      };
      
    } catch (error) {
      console.error(`Failed to highlight element:`, error);
      throw error;
    }
  }

  async clearHighlights(tabId) {
    try {
      await this.sendCommand(tabId, 'Overlay.hideHighlight');
      return { cleared: true };
      
    } catch (error) {
      console.warn(`Failed to clear highlights for tab ${tabId}:`, error);
      return { cleared: false, error: error.message };
    }
  }

  // Precise actions via CDP input domain
  async clickByCoordinates(tabId, x, y, options = {}) {
    try {
      await this.attachToTab(tabId);
      const click = async (type) => {
        await this.sendCommand(tabId, 'Input.dispatchMouseEvent', {
          type,
          x: Math.round(x),
          y: Math.round(y),
          button: 'left',
          clickCount: 1,
        });
      };
      await click('mousePressed');
      await click('mouseReleased');
      return { success: true, x, y, action: 'click_coordinates' };
    } catch (error) {
      console.error('Failed to click by coordinates:', error);
      throw error;
    }
  }

  async insertText(tabId, text) {
    try {
      await this.attachToTab(tabId);
      await this.sendCommand(tabId, 'Input.insertText', { text });
      return { success: true, text };
    } catch (error) {
      console.error('Failed to insert text:', error);
      throw error;
    }
  }

  // Event handling for DOM changes
  onDocumentUpdated(tabId) {
    console.log(`Document updated in tab ${tabId}, rebuilding DOM tree...`);
    
    // Rebuild DOM tree after document changes
    const domBuilder = this.domBuilders.get(tabId);
    if (domBuilder) {
      domBuilder.invalidateCache();
    }
  }

  onElementInspected(tabId, params) {
    console.log(`Element inspected in tab ${tabId}:`, params);
    
    // Could be used for interactive element selection
    // For now, just log the event
  }

  // Cleanup method
  async cleanup() {
    console.log('Cleaning up CDP Manager...');
    
    const tabIds = Array.from(this.connections.keys());
    await Promise.all(tabIds.map(tabId => this.detachFromTab(tabId)));
    
    this.connections.clear();
    this.domBuilders.clear();
    this.initialized = false;
    
    console.log('CDP Manager cleanup complete');
  }
}

// Export for use by other modules
if (typeof window !== 'undefined') {
  window.CDPManager = CDPManager;
}
