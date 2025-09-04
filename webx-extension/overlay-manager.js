/**
 * Overlay Manager - Manages visual overlays and feedback
 * Provides visual feedback for CDP operations and element interactions
 */

class OverlayManager {
  constructor() {
    this.overlays = new Map(); // tabId -> overlay data
    this.activeHighlights = new Map(); // tabId -> Set of highlighted nodeIds
    this.overlayCounter = 0;
  }

  async initialize() {
    console.log('Overlay Manager initialized');
  }

  async createElementOverlay(tabId, elementData, options = {}) {
    const {
      type = 'highlight',
      color = '#FF6B6B',
      opacity = 0.3,
      duration = null, // null = permanent, number = ms
      showLabel = true,
      animation = null
    } = options;

    const overlayId = `overlay_${++this.overlayCounter}`;
    
    try {
      // Create overlay via CDP Runtime evaluation
      const result = await chrome.debugger.sendCommand(
        { tabId }, 
        'Runtime.evaluate',
        {
          expression: `
            (function() {
              const overlay = document.createElement('div');
              overlay.id = '${overlayId}';
              overlay.className = 'webx-overlay webx-overlay-${type}';
              overlay.style.cssText = \`
                position: absolute !important;
                pointer-events: none !important;
                z-index: 999998 !important;
                border: 2px solid ${color} !important;
                background: ${color.replace('#', 'rgba(').replace(/(.{2})(.{2})(.{2})/, '$1, $2, $3')}${opacity}) !important;
                border-radius: 4px !important;
                box-shadow: 0 0 10px rgba(0,0,0,0.3) !important;
                transition: all 0.3s ease !important;
                left: ${elementData.rect.x}px !important;
                top: ${elementData.rect.y}px !important;
                width: ${elementData.rect.width}px !important;
                height: ${elementData.rect.height}px !important;
              \`;
              
              ${showLabel ? `
                const label = document.createElement('div');
                label.className = 'webx-overlay-label';
                label.textContent = '${elementData.labelId || 'Element'}';
                label.style.cssText = \`
                  position: absolute !important;
                  top: -25px !important;
                  right: 0 !important;
                  background: ${color} !important;
                  color: white !important;
                  padding: 2px 6px !important;
                  border-radius: 3px !important;
                  font-size: 11px !important;
                  font-family: monospace !important;
                  font-weight: bold !important;
                \`;
                overlay.appendChild(label);
              ` : ''}
              
              ${animation ? `
                overlay.style.animation = '${animation}';
              ` : ''}
              
              document.body.appendChild(overlay);
              
              ${duration ? `
                setTimeout(() => {
                  const el = document.getElementById('${overlayId}');
                  if (el) el.remove();
                }, ${duration});
              ` : ''}
              
              return { success: true, overlayId: '${overlayId}' };
            })()
          `
        }
      );

      // Store overlay data
      if (!this.overlays.has(tabId)) {
        this.overlays.set(tabId, new Map());
      }
      
      this.overlays.get(tabId).set(overlayId, {
        id: overlayId,
        type,
        elementData,
        options,
        timestamp: Date.now()
      });

      console.log(`Created ${type} overlay ${overlayId} for tab ${tabId}`);
      
      return { success: true, overlayId };
      
    } catch (error) {
      console.error(`Failed to create overlay:`, error);
      return { success: false, error: error.message };
    }
  }

  async removeOverlay(tabId, overlayId) {
    try {
      await chrome.debugger.sendCommand(
        { tabId },
        'Runtime.evaluate',
        {
          expression: `
            (function() {
              const overlay = document.getElementById('${overlayId}');
              if (overlay) {
                overlay.remove();
                return { removed: true };
              }
              return { removed: false };
            })()
          `
        }
      );

      // Remove from our tracking
      const tabOverlays = this.overlays.get(tabId);
      if (tabOverlays) {
        tabOverlays.delete(overlayId);
        if (tabOverlays.size === 0) {
          this.overlays.delete(tabId);
        }
      }

      console.log(`Removed overlay ${overlayId} from tab ${tabId}`);
      return { success: true, removed: true };
      
    } catch (error) {
      console.error(`Failed to remove overlay ${overlayId}:`, error);
      return { success: false, error: error.message };
    }
  }

  async clearAllOverlays(tabId) {
    try {
      await chrome.debugger.sendCommand(
        { tabId },
        'Runtime.evaluate',
        {
          expression: `
            (function() {
              const overlays = document.querySelectorAll('.webx-overlay');
              let removed = 0;
              overlays.forEach(overlay => {
                overlay.remove();
                removed++;
              });
              return { removed };
            })()
          `
        }
      );

      // Clear our tracking
      this.overlays.delete(tabId);

      console.log(`Cleared all overlays for tab ${tabId}`);
      return { success: true };
      
    } catch (error) {
      console.error(`Failed to clear overlays for tab ${tabId}:`, error);
      return { success: false, error: error.message };
    }
  }

  async highlightElement(tabId, elementData, options = {}) {
    const highlightOptions = {
      type: 'highlight',
      color: options.color || '#FF6B6B',
      opacity: options.opacity || 0.3,
      showLabel: options.showLabel !== false,
      animation: options.pulse ? 'webx-pulse 1s ease-in-out infinite' : null,
      ...options
    };

    return await this.createElementOverlay(tabId, elementData, highlightOptions);
  }

  async showClickFeedback(tabId, elementData, options = {}) {
    const clickOptions = {
      type: 'click-feedback',
      color: options.color || '#4CAF50',
      opacity: 0.6,
      duration: 800,
      showLabel: false,
      animation: 'webx-click-ripple 0.8s ease-out',
      ...options
    };

    return await this.createElementOverlay(tabId, elementData, clickOptions);
  }

  async showFillFeedback(tabId, elementData, text, options = {}) {
    const fillOptions = {
      type: 'fill-feedback',
      color: options.color || '#2196F3',
      opacity: 0.4,
      duration: 1200,
      showLabel: true,
      labelText: `Filled: "${text.substring(0, 20)}${text.length > 20 ? '...' : ''}"`,
      ...options
    };

    // Create custom overlay with fill text
    return await this.createCustomOverlay(tabId, elementData, fillOptions);
  }

  async createCustomOverlay(tabId, elementData, options) {
    const overlayId = `overlay_${++this.overlayCounter}`;
    
    try {
      const result = await chrome.debugger.sendCommand(
        { tabId },
        'Runtime.evaluate',
        {
          expression: `
            (function() {
              const overlay = document.createElement('div');
              overlay.id = '${overlayId}';
              overlay.className = 'webx-overlay webx-overlay-${options.type}';
              overlay.style.cssText = \`
                position: absolute !important;
                pointer-events: none !important;
                z-index: 999998 !important;
                border: 2px solid ${options.color} !important;
                background: ${options.color.replace('#', 'rgba(').replace(/(.{2})(.{2})(.{2})/, '$1, $2, $3')}, ${options.opacity}) !important;
                border-radius: 4px !important;
                box-shadow: 0 0 10px rgba(0,0,0,0.3) !important;
                transition: all 0.3s ease !important;
                left: ${elementData.rect.x}px !important;
                top: ${elementData.rect.y}px !important;
                width: ${elementData.rect.width}px !important;
                height: ${elementData.rect.height}px !important;
              \`;
              
              ${options.labelText ? `
                const label = document.createElement('div');
                label.className = 'webx-overlay-label';
                label.textContent = '${options.labelText}';
                label.style.cssText = \`
                  position: absolute !important;
                  top: -30px !important;
                  left: 0 !important;
                  background: ${options.color} !important;
                  color: white !important;
                  padding: 4px 8px !important;
                  border-radius: 3px !important;
                  font-size: 11px !important;
                  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                  font-weight: 500 !important;
                  white-space: nowrap !important;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
                \`;
                overlay.appendChild(label);
              ` : ''}
              
              // Add CSS animations if not already present
              if (!document.getElementById('webx-overlay-styles')) {
                const style = document.createElement('style');
                style.id = 'webx-overlay-styles';
                style.textContent = \`
                  @keyframes webx-pulse {
                    0%, 100% { opacity: ${options.opacity}; transform: scale(1); }
                    50% { opacity: ${Math.min(options.opacity + 0.3, 1)}; transform: scale(1.02); }
                  }
                  
                  @keyframes webx-click-ripple {
                    0% { transform: scale(1); opacity: 0.6; }
                    100% { transform: scale(1.2); opacity: 0; }
                  }
                  
                  .webx-overlay-click-feedback {
                    border-radius: 50% !important;
                  }
                \`;
                document.head.appendChild(style);
              }
              
              ${options.animation ? `
                overlay.style.animation = '${options.animation}';
              ` : ''}
              
              document.body.appendChild(overlay);
              
              ${options.duration ? `
                setTimeout(() => {
                  const el = document.getElementById('${overlayId}');
                  if (el) {
                    el.style.opacity = '0';
                    setTimeout(() => el.remove(), 300);
                  }
                }, ${options.duration});
              ` : ''}
              
              return { success: true, overlayId: '${overlayId}' };
            })()
          `
        }
      );

      return { success: true, overlayId };
      
    } catch (error) {
      console.error(`Failed to create custom overlay:`, error);
      return { success: false, error: error.message };
    }
  }

  async showProgress(tabId, message, options = {}) {
    const {
      position = 'top-right',
      duration = 3000,
      type = 'info' // info, success, warning, error
    } = options;

    const overlayId = `progress_${++this.overlayCounter}`;
    const colors = {
      info: '#2196F3',
      success: '#4CAF50',
      warning: '#FF9800',
      error: '#F44336'
    };

    try {
      await chrome.debugger.sendCommand(
        { tabId },
        'Runtime.evaluate',
        {
          expression: `
            (function() {
              const progress = document.createElement('div');
              progress.id = '${overlayId}';
              progress.className = 'webx-progress webx-progress-${type}';
              progress.textContent = '${message}';
              
              const positions = {
                'top-right': 'top: 20px; right: 20px;',
                'top-left': 'top: 20px; left: 20px;',
                'bottom-right': 'bottom: 20px; right: 20px;',
                'bottom-left': 'bottom: 20px; left: 20px;',
                'center': 'top: 50%; left: 50%; transform: translate(-50%, -50%);'
              };
              
              progress.style.cssText = \`
                position: fixed !important;
                \${positions['${position}'] || positions['top-right']}
                background: ${colors[type]} !important;
                color: white !important;
                padding: 12px 16px !important;
                border-radius: 6px !important;
                font-size: 13px !important;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                font-weight: 500 !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
                z-index: 999999 !important;
                pointer-events: none !important;
                max-width: 300px !important;
                word-wrap: break-word !important;
                opacity: 0 !important;
                transform: translateY(-10px) !important;
                transition: all 0.3s ease !important;
              \`;
              
              document.body.appendChild(progress);
              
              // Animate in
              requestAnimationFrame(() => {
                progress.style.opacity = '1';
                progress.style.transform = 'translateY(0)';
              });
              
              // Auto remove
              setTimeout(() => {
                progress.style.opacity = '0';
                progress.style.transform = 'translateY(-10px)';
                setTimeout(() => progress.remove(), 300);
              }, ${duration});
              
              return { success: true, progressId: '${overlayId}' };
            })()
          `
        }
      );

      console.log(`Showed progress message: ${message}`);
      return { success: true, overlayId };
      
    } catch (error) {
      console.error(`Failed to show progress message:`, error);
      return { success: false, error: error.message };
    }
  }

  async getOverlayStats(tabId) {
    const tabOverlays = this.overlays.get(tabId);
    if (!tabOverlays) {
      return { count: 0, overlays: [] };
    }

    return {
      count: tabOverlays.size,
      overlays: Array.from(tabOverlays.values()).map(overlay => ({
        id: overlay.id,
        type: overlay.type,
        age: Date.now() - overlay.timestamp
      }))
    };
  }

  cleanup(tabId = null) {
    if (tabId) {
      this.overlays.delete(tabId);
      this.activeHighlights.delete(tabId);
    } else {
      this.overlays.clear();
      this.activeHighlights.clear();
      this.overlayCounter = 0;
    }
  }
}

// Export for use by other modules
if (typeof window !== 'undefined') {
  window.OverlayManager = OverlayManager;
}