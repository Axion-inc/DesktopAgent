/**
 * DOM Builder - Creates numbered element trees similar to buildDomTree.js
 * Provides intelligent element extraction with visual numbering
 * 
 * This module builds interactive DOM trees with numbered labels for easy
 * element identification and selection, similar to the original buildDomTree.js approach.
 */

class DOMBuilder {
  constructor(cdpConnection) {
    this.connection = cdpConnection;
    this.elementMap = new Map(); // nodeId -> element data
    this.labelMap = new Map(); // labelId -> element data  
    this.labelOverlays = new Map(); // nodeId -> overlay element
    this.nextLabelId = 1;
    this.documentRoot = null;
    this.treeCache = null;
    this.cacheTimestamp = 0;
    this.cacheTTL = 5000; // 5 seconds cache
  }

  async initialize() {
    try {
      const { tabId } = this.connection;
      
      // Get document root
      const docResult = await this.sendCommand('DOM.getDocument', { depth: -1 });
      this.documentRoot = docResult.root;
      
      console.log(`DOM Builder initialized for tab ${tabId}`);
      
    } catch (error) {
      console.error(`Failed to initialize DOM Builder:`, error);
      throw error;
    }
  }

  async sendCommand(command, params = {}) {
    const { tabId } = this.connection;
    
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

  async buildTree(options = {}) {
    const {
      includeInvisible = false,
      includeNonInteractive = false,
      maxDepth = 10,
      addNumberedLabels = true,
      forceRefresh = false
    } = options;

    // Check cache validity
    if (!forceRefresh && this.treeCache && 
        (Date.now() - this.cacheTimestamp < this.cacheTTL)) {
      console.log('Returning cached DOM tree');
      return this.treeCache;
    }

    try {
      // Clear previous state
      this.elementMap.clear();
      this.labelMap.clear();
      await this.clearLabels();
      this.nextLabelId = 1;

      // Refresh document if needed
      if (forceRefresh || !this.documentRoot) {
        const docResult = await this.sendCommand('DOM.getDocument', { depth: -1 });
        this.documentRoot = docResult.root;
      }

      console.log(`Building DOM tree with options:`, options);

      const tree = await this.traverseDOM(this.documentRoot, {
        includeInvisible,
        includeNonInteractive,
        maxDepth,
        currentDepth: 0
      });

      if (addNumberedLabels) {
        await this.addVisualLabels();
      }

      // Cache result
      this.treeCache = {
        tree,
        elementMap: Object.fromEntries(this.elementMap),
        labelMap: Object.fromEntries(this.labelMap),
        labelCount: this.nextLabelId - 1,
        options,
        timestamp: Date.now()
      };
      
      this.cacheTimestamp = Date.now();

      console.log(`DOM tree built with ${this.nextLabelId - 1} labeled elements`);
      
      return this.treeCache;
      
    } catch (error) {
      console.error(`Failed to build DOM tree:`, error);
      throw error;
    }
  }

  async traverseDOM(node, options) {
    const { maxDepth, currentDepth, includeInvisible, includeNonInteractive } = options;
    
    if (currentDepth >= maxDepth) return null;

    try {
      // Get node details
      const nodeData = await this.getNodeDetails(node);
      
      // Filter non-interactive/invisible elements if requested
      if (!includeNonInteractive && !this.isInteractiveElement(nodeData)) {
        // Still process children for interactive descendants
        if (node.children) {
          const children = [];
          for (const child of node.children) {
            const childElement = await this.traverseDOM(child, {
              ...options,
              currentDepth: currentDepth + 1
            });
            if (childElement) {
              children.push(childElement);
            }
          }
          return children.length > 0 ? { children, ...nodeData, isContainer: true } : null;
        }
        return null;
      }

      if (!includeInvisible && !nodeData.visible) {
        return null;
      }

      // Create labeled element
      const labelId = this.nextLabelId++;
      const labeledElement = {
        labelId,
        nodeId: node.nodeId,
        tagName: nodeData.tagName,
        text: nodeData.textContent,
        attributes: nodeData.attributes,
        rect: nodeData.boundingBox,
        interactive: this.isInteractiveElement(nodeData),
        visible: nodeData.visible,
        role: nodeData.role,
        inputType: nodeData.inputType,
        children: [],
        depth: currentDepth
      };

      // Store in maps for quick lookup
      this.elementMap.set(node.nodeId, labeledElement);
      this.labelMap.set(labelId, labeledElement);

      // Process children
      if (node.children) {
        for (const child of node.children) {
          const childElement = await this.traverseDOM(child, {
            ...options,
            currentDepth: currentDepth + 1
          });
          
          if (childElement) {
            if (Array.isArray(childElement)) {
              labeledElement.children.push(...childElement);
            } else {
              labeledElement.children.push(childElement);
            }
          }
        }
      }

      return labeledElement;
      
    } catch (error) {
      console.warn(`Error traversing node ${node.nodeId}:`, error);
      return null;
    }
  }

  async getNodeDetails(node) {
    try {
      // Process attributes
      const attributes = {};
      if (node.attributes) {
        for (let i = 0; i < node.attributes.length; i += 2) {
          attributes[node.attributes[i]] = node.attributes[i + 1];
        }
      }

      // Get bounding box
      let boundingBox = null;
      let visible = false;
      
      try {
        const boxResult = await this.sendCommand('DOM.getBoxModel', { 
          nodeId: node.nodeId 
        });
        
        if (boxResult && boxResult.model && boxResult.model.content) {
          const [x1, y1, x2, y2, x3, y3, x4, y4] = boxResult.model.content;
          const x = Math.min(x1, x2, x3, x4);
          const y = Math.min(y1, y2, y3, y4);
          const width = Math.max(x1, x2, x3, x4) - x;
          const height = Math.max(y1, y2, y3, y4) - y;
          
          boundingBox = { x, y, width, height };
          visible = width > 0 && height > 0;
        }
      } catch (e) {
        // Element might not have a box model (e.g., text nodes, hidden elements)
      }

      // Get text content safely
      let textContent = '';
      try {
        if (node.nodeType === 3) { // Text node
          textContent = node.nodeValue || '';
        } else {
          // Try to get text content via runtime evaluation
          const objectResult = await this.sendCommand('DOM.resolveNode', {
            nodeId: node.nodeId
          });
          
          if (objectResult && objectResult.object) {
            const textResult = await this.sendCommand('Runtime.callFunctionOn', {
              functionDeclaration: `
                function() {
                  if (this.nodeType === 3) return this.nodeValue || '';
                  return this.textContent ? this.textContent.trim() : '';
                }
              `,
              objectId: objectResult.object.objectId
            });
            
            if (textResult && textResult.result && textResult.result.value) {
              textContent = textResult.result.value.substring(0, 200); // Limit text length
            }
          }
        }
      } catch (e) {
        // Fallback to node value if available
        textContent = node.nodeValue || '';
      }

      // Determine input type for input elements
      let inputType = null;
      if (node.nodeName && node.nodeName.toLowerCase() === 'input') {
        inputType = attributes.type || 'text';
      }

      return {
        nodeId: node.nodeId,
        tagName: node.nodeName?.toLowerCase() || '',
        textContent: textContent.trim(),
        attributes,
        boundingBox,
        visible,
        role: attributes.role || this.inferRole(node.nodeName, attributes),
        inputType,
        nodeType: node.nodeType
      };
      
    } catch (error) {
      console.warn(`Error getting node details for ${node.nodeId}:`, error);
      return {
        nodeId: node.nodeId,
        tagName: node.nodeName?.toLowerCase() || '',
        textContent: '',
        attributes: {},
        boundingBox: null,
        visible: false,
        role: 'generic',
        inputType: null,
        nodeType: node.nodeType
      };
    }
  }

  isInteractiveElement(nodeData) {
    const { tagName, attributes, role } = nodeData;
    
    // Interactive HTML tags
    const interactiveTags = [
      'button', 'input', 'select', 'textarea', 'a', 'label',
      'summary', 'details'
    ];
    
    // Interactive ARIA roles
    const interactiveRoles = [
      'button', 'link', 'textbox', 'combobox', 'checkbox', 'radio',
      'slider', 'spinbutton', 'searchbox', 'switch', 'tab', 'menuitem'
    ];

    // Check tag name
    if (interactiveTags.includes(tagName)) {
      return true;
    }

    // Check ARIA role
    if (interactiveRoles.includes(role)) {
      return true;
    }

    // Check for event handlers (common patterns)
    const hasClickHandler = attributes.onclick || 
                           attributes['ng-click'] ||
                           attributes['v-on:click'] ||
                           attributes['@click'] ||
                           attributes['data-action'] ||
                           attributes.href;

    // Check for tabindex (makes element focusable)
    const hasFocusability = attributes.tabindex !== undefined;
    
    // Check for contenteditable
    const isEditable = attributes.contenteditable === 'true';

    return hasClickHandler || hasFocusability || isEditable;
  }

  inferRole(tagName, attributes) {
    const roleMap = {
      'button': 'button',
      'input': this.inferInputRole(attributes.type),
      'select': 'combobox',
      'textarea': 'textbox',
      'a': attributes.href ? 'link' : 'generic',
      'img': 'img',
      'h1': 'heading',
      'h2': 'heading',
      'h3': 'heading',
      'h4': 'heading',
      'h5': 'heading',
      'h6': 'heading',
      'nav': 'navigation',
      'main': 'main',
      'header': 'banner',
      'footer': 'contentinfo',
      'aside': 'complementary',
      'section': 'region',
      'article': 'article',
      'form': 'form',
      'table': 'table',
      'ul': 'list',
      'ol': 'list',
      'li': 'listitem'
    };

    return attributes.role || roleMap[tagName?.toLowerCase()] || 'generic';
  }

  inferInputRole(inputType) {
    const inputRoles = {
      'text': 'textbox',
      'email': 'textbox',
      'password': 'textbox',
      'search': 'searchbox',
      'url': 'textbox',
      'tel': 'textbox',
      'number': 'spinbutton',
      'range': 'slider',
      'checkbox': 'checkbox',
      'radio': 'radio',
      'file': 'button',
      'submit': 'button',
      'button': 'button',
      'reset': 'button',
      'image': 'button'
    };

    return inputRoles[inputType] || 'textbox';
  }

  async addVisualLabels() {
    try {
      // Inject label styles first
      await this.injectLabelStyles();
      
      // Add labels for each interactive element
      let addedCount = 0;
      for (const [nodeId, elementData] of this.elementMap) {
        if (elementData.interactive && elementData.visible && elementData.rect) {
          try {
            await this.addLabelToElement(nodeId, elementData);
            addedCount++;
          } catch (error) {
            console.warn(`Failed to add label to element ${nodeId}:`, error);
          }
        }
      }
      
      console.log(`Added ${addedCount} visual labels`);
      
    } catch (error) {
      console.error(`Failed to add visual labels:`, error);
      throw error;
    }
  }

  async injectLabelStyles() {
    try {
      await this.sendCommand('Runtime.evaluate', {
        expression: `
          (function() {
            if (document.getElementById('webx-label-styles')) return;
            
            const style = document.createElement('style');
            style.id = 'webx-label-styles';
            style.textContent = \`
              .webx-element-label {
                position: absolute !important;
                background: #FF6B6B !important;
                color: white !important;
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', monospace !important;
                font-size: 11px !important;
                font-weight: 600 !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border: 1px solid #FF5252 !important;
                z-index: 999999 !important;
                pointer-events: none !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
                line-height: 1.2 !important;
                min-width: 18px !important;
                text-align: center !important;
                backdrop-filter: blur(2px) !important;
                user-select: none !important;
                transform: translateZ(0) !important;
              }
              
              .webx-element-highlight {
                outline: 2px solid #FF6B6B !important;
                outline-offset: 1px !important;
                position: relative !important;
              }
              
              .webx-element-highlight::after {
                content: '' !important;
                position: absolute !important;
                top: -2px !important;
                left: -2px !important;
                right: -2px !important;
                bottom: -2px !important;
                background: rgba(255, 107, 107, 0.1) !important;
                pointer-events: none !important;
                border-radius: 2px !important;
              }
              
              @keyframes webx-pulse {
                0% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.7; transform: scale(1.05); }
                100% { opacity: 1; transform: scale(1); }
              }
              
              .webx-element-label.webx-active {
                animation: webx-pulse 0.6s ease-in-out !important;
              }
            \`;
            
            document.head.appendChild(style);
            return true;
          })()
        `
      });
      
    } catch (error) {
      console.warn(`Failed to inject label styles:`, error);
    }
  }

  async addLabelToElement(nodeId, elementData) {
    const { labelId, rect } = elementData;
    
    try {
      await this.sendCommand('Runtime.evaluate', {
        expression: `
          (function() {
            try {
              // Remove existing label if any
              const existingLabel = document.querySelector('.webx-element-label[data-node-id="${nodeId}"]');
              if (existingLabel) existingLabel.remove();

              // Get the actual element to attach label to
              const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_ELEMENT,
                null,
                false
              );
              
              let targetElement = null;
              let currentNode;
              while (currentNode = walker.nextNode()) {
                // This is a simplified approach - in real implementation,
                // we'd need a more robust way to match CDP nodeId to DOM element
                if (currentNode.tagName && currentNode.getBoundingClientRect) {
                  const rect = currentNode.getBoundingClientRect();
                  if (Math.abs(rect.x - ${rect.x}) < 5 && 
                      Math.abs(rect.y - ${rect.y}) < 5 &&
                      Math.abs(rect.width - ${rect.width}) < 5 &&
                      Math.abs(rect.height - ${rect.height}) < 5) {
                    targetElement = currentNode;
                    break;
                  }
                }
              }
              
              // Create label
              const label = document.createElement('div');
              label.className = 'webx-element-label';
              label.setAttribute('data-node-id', '${nodeId}');
              label.setAttribute('data-label-id', '${labelId}');
              label.textContent = '${labelId}';
              
              // Position label at top-right of element
              const labelX = ${rect.x + rect.width - 25};
              const labelY = ${rect.y - 8};
              
              label.style.left = Math.max(5, labelX) + 'px';
              label.style.top = Math.max(5, labelY) + 'px';
              
              document.body.appendChild(label);
              
              // Add highlight to target element if found
              if (targetElement) {
                targetElement.classList.add('webx-element-highlight');
                targetElement.setAttribute('data-webx-label', '${labelId}');
                targetElement.setAttribute('data-webx-node-id', '${nodeId}');
              }
              
              return { success: true, labelId: ${labelId} };
              
            } catch (error) {
              return { success: false, error: error.message };
            }
          })()
        `
      });
      
    } catch (error) {
      console.warn(`Failed to add label to element ${nodeId}:`, error);
      throw error;
    }
  }

  async clearLabels() {
    try {
      await this.sendCommand('Runtime.evaluate', {
        expression: `
          (function() {
            try {
              // Remove all labels
              document.querySelectorAll('.webx-element-label').forEach(el => el.remove());
              
              // Remove all highlights
              document.querySelectorAll('.webx-element-highlight').forEach(el => {
                el.classList.remove('webx-element-highlight');
                el.removeAttribute('data-webx-label');
                el.removeAttribute('data-webx-node-id');
              });
              
              return { cleared: true };
              
            } catch (error) {
              return { cleared: false, error: error.message };
            }
          })()
        `
      });
      
    } catch (error) {
      console.warn(`Failed to clear labels:`, error);
    }
  }

  async findElement(selector, options = {}) {
    const { text, role, labelId, tagName, inputType } = options;

    // If searching by label ID, return directly from cache
    if (labelId) {
      const element = this.labelMap.get(parseInt(labelId));
      return element || null;
    }

    // Build tree if not cached or cache is stale
    if (!this.treeCache || (Date.now() - this.cacheTimestamp >= this.cacheTTL)) {
      await this.buildTree({ addNumberedLabels: false });
    }

    // Search through cached elements
    const candidates = Array.from(this.elementMap.values()).filter(element => {
      let matches = true;

      // Text matching (case-insensitive, partial)
      if (text) {
        const elementText = element.text || '';
        matches = matches && elementText.toLowerCase().includes(text.toLowerCase());
      }

      // Role matching
      if (role) {
        matches = matches && element.role === role;
      }

      // Tag name matching
      if (tagName) {
        matches = matches && element.tagName === tagName.toLowerCase();
      }

      // Input type matching
      if (inputType && element.tagName === 'input') {
        matches = matches && element.inputType === inputType;
      }

      // Must be interactive unless explicitly looking for non-interactive
      if (options.includeNonInteractive !== true) {
        matches = matches && element.interactive;
      }

      // Must be visible unless explicitly looking for hidden
      if (options.includeInvisible !== true) {
        matches = matches && element.visible;
      }

      return matches;
    });

    // If we have a CSS selector and multiple candidates, validate with DOM
    if (selector && candidates.length > 1) {
      for (const candidate of candidates) {
        try {
          const result = await this.sendCommand('Runtime.evaluate', {
            expression: `
              (function() {
                try {
                  const element = document.querySelector('${selector.replace(/'/g, "\\'")}');
                  if (!element) return false;
                  
                  const rect = element.getBoundingClientRect();
                  const expectedRect = ${JSON.stringify(candidate.rect)};
                  
                  return Math.abs(rect.x - expectedRect.x) < 5 &&
                         Math.abs(rect.y - expectedRect.y) < 5 &&
                         Math.abs(rect.width - expectedRect.width) < 5 &&
                         Math.abs(rect.height - expectedRect.height) < 5;
                         
                } catch (e) {
                  return false;
                }
              })()
            `
          });
          
          if (result && result.result && result.result.value === true) {
            return candidate;
          }
          
        } catch (e) {
          // Continue to next candidate
        }
      }
    }

    // Return best match (first candidate or closest text match)
    if (candidates.length > 0) {
      if (text && candidates.length > 1) {
        // Sort by text relevance
        candidates.sort((a, b) => {
          const aText = (a.text || '').toLowerCase();
          const bText = (b.text || '').toLowerCase();
          const searchText = text.toLowerCase();
          
          const aExact = aText === searchText;
          const bExact = bText === searchText;
          
          if (aExact && !bExact) return -1;
          if (bExact && !aExact) return 1;
          
          const aStarts = aText.startsWith(searchText);
          const bStarts = bText.startsWith(searchText);
          
          if (aStarts && !bStarts) return -1;
          if (bStarts && !aStarts) return 1;
          
          return aText.length - bText.length; // Prefer shorter text
        });
      }
      
      return candidates[0];
    }

    return null;
  }

  // Cache management
  invalidateCache() {
    this.treeCache = null;
    this.cacheTimestamp = 0;
    console.log('DOM cache invalidated');
  }

  isCacheValid() {
    return this.treeCache && (Date.now() - this.cacheTimestamp < this.cacheTTL);
  }

  // Get element by label ID (for quick access)
  getElementByLabel(labelId) {
    return this.labelMap.get(parseInt(labelId)) || null;
  }

  // Get element statistics
  getStats() {
    if (!this.treeCache) {
      return { totalElements: 0, interactiveElements: 0, visibleElements: 0 };
    }

    const elements = Array.from(this.elementMap.values());
    return {
      totalElements: elements.length,
      interactiveElements: elements.filter(e => e.interactive).length,
      visibleElements: elements.filter(e => e.visible).length,
      labeledElements: this.labelMap.size,
      cacheAge: Date.now() - this.cacheTimestamp
    };
  }
}

// Export for use by other modules
if (typeof window !== 'undefined') {
  window.DOMBuilder = DOMBuilder;
}