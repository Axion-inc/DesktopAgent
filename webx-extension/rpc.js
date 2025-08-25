// Desktop Agent WebX - RPC Interface
// Injected into page context to provide seamless JavaScript access

(function() {
  'use strict';
  
  // Prevent multiple injections
  if (window.DesktopAgentWebX) {
    return;
  }
  
  class DesktopAgentWebXRPC {
    constructor() {
      this.messageId = 0;
      this.pendingRequests = new Map();
      this.setupMessageListener();
    }
    
    setupMessageListener() {
      window.addEventListener('message', (event) => {
        // Only accept messages from same origin
        if (event.origin !== window.location.origin) {
          return;
        }
        
        if (event.data && event.data.type === 'webx_rpc_response') {
          const { id, result, error } = event.data;
          
          if (this.pendingRequests.has(id)) {
            const { resolve, reject } = this.pendingRequests.get(id);
            this.pendingRequests.delete(id);
            
            if (error) {
              reject(new Error(error));
            } else {
              resolve(result);
            }
          }
        }
      });
    }
    
    async sendRPC(method, params = {}) {
      const id = ++this.messageId;
      
      return new Promise((resolve, reject) => {
        // Store the promise handlers
        this.pendingRequests.set(id, { resolve, reject });
        
        // Set timeout
        setTimeout(() => {
          if (this.pendingRequests.has(id)) {
            this.pendingRequests.delete(id);
            reject(new Error('RPC request timeout'));
          }
        }, 30000);
        
        // Send message to content script
        window.postMessage({
          type: 'webx_rpc_request',
          id,
          method,
          params
        }, window.location.origin);
      });
    }
    
    // Convenience methods that mirror the DSL actions
    
    async click(selector, options = {}) {
      return await this.sendRPC('click_element', {
        selector,
        ...options
      });
    }
    
    async clickByText(text, options = {}) {
      return await this.sendRPC('click_element', {
        text,
        ...options
      });
    }
    
    async fill(selector, text, options = {}) {
      return await this.sendRPC('fill_input', {
        selector,
        text,
        ...options
      });
    }
    
    async fillByLabel(label, text, options = {}) {
      return await this.sendRPC('fill_input', {
        label,
        text,
        ...options
      });
    }
    
    async getElement(selector, options = {}) {
      return await this.sendRPC('get_element', {
        selector,
        ...options
      });
    }
    
    async waitForElement(selector, options = {}) {
      return await this.sendRPC('wait_for_element', {
        selector,
        timeout: options.timeout || 10000,
        ...options
      });
    }
    
    async getPageInfo() {
      return await this.sendRPC('get_page_info');
    }
    
    async uploadFile(selector, filePath, options = {}) {
      return await this.sendRPC('upload_file', {
        selector,
        file_path: filePath,
        ...options
      });
    }
    
    async downloadFile(url, filename = null) {
      return await this.sendRPC('download_file', {
        url,
        filename
      });
    }
    
    async takeScreenshot() {
      return await this.sendRPC('take_screenshot');
    }
    
    async getDOMSchema() {
      return await this.sendRPC('get_dom_schema');
    }
    
    // Utility methods
    
    isReady() {
      return document.readyState === 'complete';
    }
    
    async waitForReady(timeout = 10000) {
      if (this.isReady()) {
        return true;
      }
      
      return new Promise((resolve) => {
        const startTime = Date.now();
        
        const checkReady = () => {
          if (this.isReady()) {
            resolve(true);
          } else if (Date.now() - startTime > timeout) {
            resolve(false);
          } else {
            setTimeout(checkReady, 100);
          }
        };
        
        checkReady();
      });
    }
  }
  
  // Make the RPC interface available globally
  window.DesktopAgentWebX = new DesktopAgentWebXRPC();
  
  // Also handle messages from content script
  window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'webx_rpc_request') {
      // This would be handled by content script communication
      // For now, we'll just log it
      console.log('RPC request from page:', event.data);
    }
  });
  
})();