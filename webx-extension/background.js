// Desktop Agent WebX - Background Script
// Manages native messaging connection and message routing

class WebXBackground {
  constructor() {
    this.nativePort = null;
    this.isConnected = false;
    this.messageQueue = [];
    this.requestHandlers = new Map();
    this.requestId = 0;
    
    this.setupEventListeners();
    this.connectToNativeHost();
  }

  setupEventListeners() {
    // Handle messages from content scripts
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleContentMessage(message, sender, sendResponse);
      return true; // Keep message channel open for async response
    });
    
    // Handle extension lifecycle
    chrome.runtime.onStartup.addListener(() => {
      this.connectToNativeHost();
    });
    
    chrome.runtime.onInstalled.addListener(() => {
      console.log('Desktop Agent WebX installed');
      this.connectToNativeHost();
    });
  }

  connectToNativeHost() {
    try {
      this.nativePort = chrome.runtime.connectNative('com.desktopagent.webx');
      
      this.nativePort.onMessage.addListener((message) => {
        this.handleNativeMessage(message);
      });
      
      this.nativePort.onDisconnect.addListener(() => {
        console.log('Native messaging disconnected:', chrome.runtime.lastError);
        this.isConnected = false;
        this.nativePort = null;
        
        // Attempt to reconnect after a delay
        setTimeout(() => {
          this.connectToNativeHost();
        }, 5000);
      });
      
      this.isConnected = true;
      console.log('Connected to native messaging host');
      
      // Send handshake
      this.sendToNativeHost({
        method: 'handshake',
        params: {
          extension_id: chrome.runtime.id,
          version: chrome.runtime.getManifest().version
        }
      });
      
      // Process queued messages
      this.processMessageQueue();
      
    } catch (error) {
      console.error('Failed to connect to native host:', error);
      this.isConnected = false;
    }
  }

  sendToNativeHost(message, callback = null) {
    if (!this.isConnected || !this.nativePort) {
      console.log('Native host not connected, queuing message');
      this.messageQueue.push({ message, callback });
      this.connectToNativeHost();
      return;
    }

    // Add request ID for tracking responses
    const requestId = ++this.requestId;
    message.id = requestId;
    
    if (callback) {
      this.requestHandlers.set(requestId, callback);
      
      // Set timeout for request
      setTimeout(() => {
        if (this.requestHandlers.has(requestId)) {
          this.requestHandlers.delete(requestId);
          callback({ error: 'Request timeout' });
        }
      }, 30000); // 30 second timeout
    }

    try {
      this.nativePort.postMessage(message);
    } catch (error) {
      console.error('Failed to send message to native host:', error);
      if (callback) {
        this.requestHandlers.delete(requestId);
        callback({ error: error.message });
      }
    }
  }

  handleNativeMessage(message) {
    console.log('Received from native host:', message);
    
    if (message.id && this.requestHandlers.has(message.id)) {
      // This is a response to a previous request
      const handler = this.requestHandlers.get(message.id);
      this.requestHandlers.delete(message.id);
      handler(message);
    } else {
      // This is an unsolicited message (event, notification, etc.)
      console.log('Unsolicited message from native host:', message);
    }
  }

  processMessageQueue() {
    while (this.messageQueue.length > 0 && this.isConnected) {
      const { message, callback } = this.messageQueue.shift();
      this.sendToNativeHost(message, callback);
    }
  }

  handleContentMessage(message, sender, sendResponse) {
    console.log('Received from content script:', message);
    
    // Forward RPC calls to native host
    if (message.type === 'rpc_call') {
      this.sendToNativeHost({
        method: message.method,
        params: {
          ...message.params,
          tab_id: sender.tab.id,
          frame_id: sender.frameId
        }
      }, (response) => {
        sendResponse(response);
      });
    }
    // Handle other message types as needed
    else {
      sendResponse({ error: 'Unknown message type' });
    }
  }
}

// Initialize background script
const webxBackground = new WebXBackground();