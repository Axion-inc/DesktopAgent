// Desktop Agent WebX - Content Script
// Injected into web pages to provide DOM manipulation capabilities

class WebXContent {
  constructor() {
    this.isInitialized = false;
    this.rpcHandlers = new Map();
    this.setupEventListeners();
    this.initialize();
  }

  async initialize() {
    if (this.isInitialized) return;
    
    // Inject RPC interface into page
    await this.injectRPCInterface();
    
    this.setupRPCHandlers();
    this.isInitialized = true;
    
    console.log('Desktop Agent WebX content script initialized');
  }

  setupEventListeners() {
    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'execute_rpc') {
        this.executeRPC(message.method, message.params)
          .then(result => sendResponse({ result }))
          .catch(error => sendResponse({ error: error.message }));
        return true; // Keep message channel open
      }
    });
    
    // Listen for page navigation
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        this.initialize();
      });
    } else {
      this.initialize();
    }
  }

  async injectRPCInterface() {
    // Inject the RPC library into the page context
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('rpc.js');
    script.onload = function() {
      this.remove();
    };
    (document.head || document.documentElement).appendChild(script);
  }

  setupRPCHandlers() {
    // Register DOM manipulation methods
    this.rpcHandlers.set('click_element', this.clickElement.bind(this));
    this.rpcHandlers.set('fill_input', this.fillInput.bind(this));
    this.rpcHandlers.set('get_element', this.getElement.bind(this));
    this.rpcHandlers.set('wait_for_element', this.waitForElement.bind(this));
    this.rpcHandlers.set('get_page_info', this.getPageInfo.bind(this));
    this.rpcHandlers.set('upload_file', this.uploadFile.bind(this));
    this.rpcHandlers.set('download_file', this.downloadFile.bind(this));
    this.rpcHandlers.set('take_screenshot', this.takeScreenshot.bind(this));
    this.rpcHandlers.set('get_dom_schema', this.getDOMSchema.bind(this));
  }

  async executeRPC(method, params) {
    if (!this.rpcHandlers.has(method)) {
      throw new Error(`Unknown RPC method: ${method}`);
    }
    
    const handler = this.rpcHandlers.get(method);
    return await handler(params);
  }

  // RPC Method Implementations

  async clickElement(params) {
    const { selector, text, role, timeout = 10000 } = params;
    
    const element = await this.findElement({ selector, text, role, timeout });
    if (!element) {
      throw new Error(`Element not found: ${JSON.stringify(params)}`);
    }
    
    // Scroll element into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Wait a moment for scroll to complete
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Click the element
    element.click();
    
    return { success: true, element_tag: element.tagName.toLowerCase() };
  }

  async fillInput(params) {
    const { selector, label, text, timeout = 10000 } = params;
    
    const element = await this.findElement({ selector, text: label, timeout, inputOnly: true });
    if (!element) {
      throw new Error(`Input element not found: ${JSON.stringify(params)}`);
    }
    
    // Clear existing value
    element.focus();
    element.select();
    
    // Set the value
    element.value = text;
    
    // Trigger input events
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    
    return { success: true, element_tag: element.tagName.toLowerCase() };
  }

  async getElement(params) {
    const { selector, text, role } = params;
    
    const element = await this.findElement({ selector, text, role });
    if (!element) {
      return null;
    }
    
    return {
      tagName: element.tagName.toLowerCase(),
      text: element.textContent?.trim() || '',
      value: element.value || '',
      attributes: this.getElementAttributes(element),
      rect: element.getBoundingClientRect()
    };
  }

  async waitForElement(params) {
    const { selector, text, role, timeout = 10000 } = params;
    
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      const element = await this.findElement({ selector, text, role, timeout: 100 });
      if (element) {
        return { found: true, element_info: this.getElementInfo(element) };
      }
      
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    return { found: false };
  }

  async getPageInfo() {
    return {
      title: document.title,
      url: window.location.href,
      ready_state: document.readyState,
      timestamp: Date.now()
    };
  }

  async uploadFile(params) {
    const { selector, label, file_path } = params;
    
    // Find the file input
    const element = await this.findElement({ 
      selector, 
      text: label, 
      inputOnly: true,
      inputType: 'file'
    });
    
    if (!element) {
      throw new Error(`File input not found: ${JSON.stringify(params)}`);
    }
    
    // Note: File upload requires native host to handle file selection
    // This is a placeholder - actual implementation would use chrome.debugger
    throw new Error('File upload requires debugger permissions - not implemented yet');
  }

  async downloadFile(params) {
    const { url, filename } = params;
    
    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    if (filename) {
      link.download = filename;
    }
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    return { success: true, url };
  }

  async takeScreenshot() {
    // Screenshots are handled by the background script
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ 
        type: 'rpc_call',
        method: 'take_screenshot',
        params: {}
      }, resolve);
    });
  }

  async getDOMSchema() {
    // Generate a simplified DOM schema similar to accessibility tree
    const schema = this.generateDOMSchema(document.body);
    return { schema, timestamp: Date.now() };
  }

  // Helper Methods

  async findElement(params) {
    const { selector, text, role, timeout = 1000, inputOnly = false, inputType = null } = params;
    
    // Try direct selector first
    if (selector) {
      const element = document.querySelector(selector);
      if (element && this.matchesConstraints(element, { inputOnly, inputType, role, text })) {
        return element;
      }
    }
    
    // Try finding by text and role
    if (text || role) {
      const elements = this.findElementsByTextAndRole(text, role, inputOnly, inputType);
      if (elements.length > 0) {
        return elements[0];
      }
    }
    
    // Try label-based search for inputs
    if (inputOnly && text) {
      const element = this.findInputByLabel(text);
      if (element) {
        return element;
      }
    }
    
    return null;
  }

  findElementsByTextAndRole(text, role, inputOnly = false, inputType = null) {
    const elements = [];
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT,
      {
        acceptNode: (node) => {
          if (inputOnly && !this.isInput(node)) {
            return NodeFilter.FILTER_SKIP;
          }
          if (inputType && node.type !== inputType) {
            return NodeFilter.FILTER_SKIP;
          }
          if (role && node.getAttribute('role') !== role && node.tagName.toLowerCase() !== role) {
            return NodeFilter.FILTER_SKIP;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );
    
    let node;
    while (node = walker.nextNode()) {
      const nodeText = this.getElementText(node);
      if (!text || nodeText.includes(text)) {
        elements.push(node);
      }
    }
    
    return elements;
  }

  findInputByLabel(labelText) {
    // Find by associated label
    const labels = document.querySelectorAll('label');
    for (const label of labels) {
      if (label.textContent.includes(labelText)) {
        const forAttr = label.getAttribute('for');
        if (forAttr) {
          const input = document.getElementById(forAttr);
          if (input && this.isInput(input)) {
            return input;
          }
        }
        
        // Check for nested input
        const nestedInput = label.querySelector('input, select, textarea');
        if (nestedInput) {
          return nestedInput;
        }
      }
    }
    
    // Find by placeholder
    const inputs = document.querySelectorAll('input, select, textarea');
    for (const input of inputs) {
      if (input.placeholder && input.placeholder.includes(labelText)) {
        return input;
      }
    }
    
    return null;
  }

  matchesConstraints(element, constraints) {
    const { inputOnly, inputType, role, text } = constraints;
    
    if (inputOnly && !this.isInput(element)) {
      return false;
    }
    
    if (inputType && element.type !== inputType) {
      return false;
    }
    
    if (role && element.getAttribute('role') !== role && element.tagName.toLowerCase() !== role) {
      return false;
    }
    
    if (text && !this.getElementText(element).includes(text)) {
      return false;
    }
    
    return true;
  }

  isInput(element) {
    const inputTags = ['input', 'select', 'textarea'];
    return inputTags.includes(element.tagName.toLowerCase());
  }

  getElementText(element) {
    return (element.textContent || element.value || element.placeholder || '').trim();
  }

  getElementAttributes(element) {
    const attrs = {};
    for (const attr of element.attributes) {
      attrs[attr.name] = attr.value;
    }
    return attrs;
  }

  getElementInfo(element) {
    return {
      tagName: element.tagName.toLowerCase(),
      text: this.getElementText(element),
      attributes: this.getElementAttributes(element),
      rect: element.getBoundingClientRect(),
      visible: this.isElementVisible(element)
    };
  }

  isElementVisible(element) {
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && 
           window.getComputedStyle(element).visibility !== 'hidden';
  }

  generateDOMSchema(element, depth = 0) {
    if (depth > 5) return null; // Prevent infinite recursion
    
    const schema = {
      tagName: element.tagName.toLowerCase(),
      text: this.getElementText(element).substring(0, 100), // Limit text length
      attributes: {},
      children: []
    };
    
    // Include important attributes
    const importantAttrs = ['id', 'class', 'name', 'type', 'role', 'aria-label'];
    for (const attr of importantAttrs) {
      const value = element.getAttribute(attr);
      if (value) {
        schema.attributes[attr] = value;
      }
    }
    
    // Recursively process children (limit to avoid huge schemas)
    const children = Array.from(element.children).slice(0, 10);
    for (const child of children) {
      const childSchema = this.generateDOMSchema(child, depth + 1);
      if (childSchema) {
        schema.children.push(childSchema);
      }
    }
    
    return schema;
  }
}

// Initialize content script
const webxContent = new WebXContent();