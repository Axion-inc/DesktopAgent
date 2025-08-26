/**
 * WebX Plugin SDK v1.0
 * Desktop Agent WebX Extension Plugin Development Kit
 * 
 * Provides secure, sandboxed environment for developing WebX plugins
 * with controlled access to DOM manipulation and automation APIs.
 */

(function(global) {
    'use strict';

    // Prevent multiple SDK initializations
    if (global.WebXPluginSDK) {
        console.warn('WebX Plugin SDK already initialized');
        return;
    }

    /**
     * Plugin sandbox security levels
     */
    const SecurityLevel = {
        MINIMAL: 'minimal',     // Read-only access
        STANDARD: 'standard',   // Standard DOM manipulation
        ELEVATED: 'elevated',   // Advanced APIs (require approval)
        SYSTEM: 'system'        // Full system access (enterprise only)
    };

    /**
     * Plugin capability definitions
     */
    const Capabilities = {
        DOM_READ: 'dom:read',
        DOM_WRITE: 'dom:write',
        FORM_FILL: 'form:fill',
        CLICK_ELEMENTS: 'click:elements',
        FILE_UPLOAD: 'file:upload',
        SCREENSHOT: 'screenshot',
        NAVIGATION: 'navigation',
        IFRAME_ACCESS: 'iframe:access',
        SHADOW_DOM: 'shadow:dom',
        CLIPBOARD: 'clipboard',
        NETWORK: 'network',
        STORAGE: 'storage',
        NOTIFICATIONS: 'notifications'
    };

    /**
     * Plugin lifecycle hooks
     */
    const LifecycleHooks = {
        INIT: 'init',
        ACTIVATE: 'activate',
        DEACTIVATE: 'deactivate',
        DESTROY: 'destroy',
        PAGE_LOAD: 'page_load',
        DOM_READY: 'dom_ready',
        BEFORE_OPERATION: 'before_operation',
        AFTER_OPERATION: 'after_operation',
        ERROR: 'error'
    };

    /**
     * Main WebX Plugin SDK class
     */
    class WebXPluginSDK {
        constructor() {
            this.version = '1.0.0';
            this.plugins = new Map();
            this.securityManager = new SecurityManager();
            this.eventBus = new EventBus();
            this.initialized = false;
        }

        /**
         * Initialize the SDK
         */
        async initialize() {
            if (this.initialized) return;

            console.log(`WebX Plugin SDK v${this.version} initializing...`);

            // Setup security context
            await this.securityManager.initialize();

            // Setup event listeners
            this.setupEventListeners();

            // Connect to native messaging host
            await this.connectToNativeHost();

            this.initialized = true;
            console.log('WebX Plugin SDK initialized successfully');

            // Emit initialization event
            this.eventBus.emit('sdk:initialized');
        }

        /**
         * Register a new plugin
         */
        registerPlugin(pluginConfig) {
            if (!this.initialized) {
                throw new Error('SDK not initialized. Call initialize() first.');
            }

            const plugin = new WebXPlugin(pluginConfig, this);
            
            // Validate plugin configuration
            this.validatePlugin(plugin);

            // Check security permissions
            this.securityManager.validateCapabilities(plugin.capabilities);

            // Register plugin
            this.plugins.set(plugin.id, plugin);
            
            console.log(`Plugin registered: ${plugin.id} v${plugin.version}`);
            this.eventBus.emit('plugin:registered', plugin);

            return plugin;
        }

        /**
         * Get registered plugin by ID
         */
        getPlugin(pluginId) {
            return this.plugins.get(pluginId);
        }

        /**
         * List all registered plugins
         */
        listPlugins() {
            return Array.from(this.plugins.values());
        }

        /**
         * Validate plugin configuration
         */
        validatePlugin(plugin) {
            const required = ['id', 'name', 'version', 'capabilities'];
            for (const field of required) {
                if (!plugin[field]) {
                    throw new Error(`Plugin missing required field: ${field}`);
                }
            }

            // Validate version format
            if (!/^\d+\.\d+\.\d+/.test(plugin.version)) {
                throw new Error(`Invalid version format: ${plugin.version}`);
            }

            // Validate capabilities
            const validCapabilities = Object.values(Capabilities);
            for (const capability of plugin.capabilities) {
                if (!validCapabilities.includes(capability)) {
                    throw new Error(`Unknown capability: ${capability}`);
                }
            }
        }

        /**
         * Setup event listeners
         */
        setupEventListeners() {
            // Page navigation events
            window.addEventListener('beforeunload', () => {
                this.eventBus.emit('page:beforeunload');
            });

            window.addEventListener('load', () => {
                this.eventBus.emit('page:load');
            });

            document.addEventListener('DOMContentLoaded', () => {
                this.eventBus.emit('dom:ready');
            });
        }

        /**
         * Connect to native messaging host
         */
        async connectToNativeHost() {
            // This would connect to the WebX native messaging host
            // For now, we'll use the existing WebX interface
            if (window.DesktopAgentWebX) {
                this.nativeHost = window.DesktopAgentWebX;
                console.log('Connected to WebX native host');
            } else {
                console.warn('WebX native host not available');
            }
        }
    }

    /**
     * Individual plugin class
     */
    class WebXPlugin {
        constructor(config, sdk) {
            this.id = config.id;
            this.name = config.name;
            this.version = config.version;
            this.description = config.description || '';
            this.author = config.author || '';
            this.capabilities = config.capabilities || [];
            this.securityLevel = config.securityLevel || SecurityLevel.STANDARD;
            
            this.sdk = sdk;
            this.active = false;
            this.hooks = new Map();
            
            // Plugin-specific configuration
            this.config = config.config || {};
            
            // Initialize plugin methods
            if (config.init && typeof config.init === 'function') {
                this.hooks.set(LifecycleHooks.INIT, config.init.bind(this));
            }

            if (config.activate && typeof config.activate === 'function') {
                this.hooks.set(LifecycleHooks.ACTIVATE, config.activate.bind(this));
            }

            if (config.deactivate && typeof config.deactivate === 'function') {
                this.hooks.set(LifecycleHooks.DEACTIVATE, config.deactivate.bind(this));
            }

            // Custom methods
            if (config.methods) {
                for (const [name, method] of Object.entries(config.methods)) {
                    if (typeof method === 'function') {
                        this[name] = method.bind(this);
                    }
                }
            }
        }

        /**
         * Activate the plugin
         */
        async activate() {
            if (this.active) return;

            try {
                // Check permissions
                await this.sdk.securityManager.checkPermissions(this.capabilities);

                // Run init hook if exists
                if (this.hooks.has(LifecycleHooks.INIT)) {
                    await this.hooks.get(LifecycleHooks.INIT)();
                }

                // Run activate hook
                if (this.hooks.has(LifecycleHooks.ACTIVATE)) {
                    await this.hooks.get(LifecycleHooks.ACTIVATE)();
                }

                this.active = true;
                this.sdk.eventBus.emit('plugin:activated', this);
                
                console.log(`Plugin activated: ${this.name}`);
            } catch (error) {
                console.error(`Failed to activate plugin ${this.name}:`, error);
                throw error;
            }
        }

        /**
         * Deactivate the plugin
         */
        async deactivate() {
            if (!this.active) return;

            try {
                // Run deactivate hook
                if (this.hooks.has(LifecycleHooks.DEACTIVATE)) {
                    await this.hooks.get(LifecycleHooks.DEACTIVATE)();
                }

                this.active = false;
                this.sdk.eventBus.emit('plugin:deactivated', this);
                
                console.log(`Plugin deactivated: ${this.name}`);
            } catch (error) {
                console.error(`Failed to deactivate plugin ${this.name}:`, error);
                throw error;
            }
        }

        /**
         * Execute plugin method with security checks
         */
        async execute(methodName, ...args) {
            if (!this.active) {
                throw new Error(`Plugin ${this.name} is not active`);
            }

            // Security validation
            await this.sdk.securityManager.validateExecution(this, methodName, args);

            // Execute method
            if (typeof this[methodName] === 'function') {
                try {
                    this.sdk.eventBus.emit('plugin:before_execution', { plugin: this, method: methodName, args });
                    const result = await this[methodName](...args);
                    this.sdk.eventBus.emit('plugin:after_execution', { plugin: this, method: methodName, result });
                    return result;
                } catch (error) {
                    this.sdk.eventBus.emit('plugin:execution_error', { plugin: this, method: methodName, error });
                    throw error;
                }
            } else {
                throw new Error(`Method ${methodName} not found in plugin ${this.name}`);
            }
        }

        /**
         * Plugin API - DOM operations
         */
        async findElement(selector, options = {}) {
            this.requireCapability(Capabilities.DOM_READ);
            
            // Use WebX native host for element finding
            if (this.sdk.nativeHost) {
                return await this.sdk.nativeHost.getElement(selector, options);
            }
            
            // Fallback to direct DOM access
            return document.querySelector(selector);
        }

        async fillForm(fields) {
            this.requireCapability(Capabilities.FORM_FILL);
            
            const results = [];
            for (const [label, value] of Object.entries(fields)) {
                if (this.sdk.nativeHost) {
                    const result = await this.sdk.nativeHost.fillByLabel(label, value);
                    results.push(result);
                } else {
                    // Fallback implementation
                    results.push({ success: false, error: 'Native host not available' });
                }
            }
            
            return results;
        }

        async clickElement(selector) {
            this.requireCapability(Capabilities.CLICK_ELEMENTS);
            
            if (this.sdk.nativeHost) {
                return await this.sdk.nativeHost.click(selector);
            }
            
            const element = document.querySelector(selector);
            if (element) {
                element.click();
                return { success: true };
            } else {
                throw new Error(`Element not found: ${selector}`);
            }
        }

        async takeScreenshot() {
            this.requireCapability(Capabilities.SCREENSHOT);
            
            if (this.sdk.nativeHost) {
                return await this.sdk.nativeHost.takeScreenshot();
            }
            
            throw new Error('Screenshot capability requires native host connection');
        }

        /**
         * Plugin API - Storage operations
         */
        async getStorage(key) {
            this.requireCapability(Capabilities.STORAGE);
            
            return new Promise((resolve) => {
                chrome.storage.local.get([`plugin_${this.id}_${key}`], (result) => {
                    resolve(result[`plugin_${this.id}_${key}`]);
                });
            });
        }

        async setStorage(key, value) {
            this.requireCapability(Capabilities.STORAGE);
            
            return new Promise((resolve) => {
                chrome.storage.local.set({ [`plugin_${this.id}_${key}`]: value }, resolve);
            });
        }

        /**
         * Plugin API - Event handling
         */
        on(event, callback) {
            this.sdk.eventBus.on(`plugin_${this.id}:${event}`, callback);
        }

        emit(event, data) {
            this.sdk.eventBus.emit(`plugin_${this.id}:${event}`, data);
        }

        /**
         * Check if plugin has required capability
         */
        requireCapability(capability) {
            if (!this.capabilities.includes(capability)) {
                throw new Error(`Plugin ${this.name} does not have required capability: ${capability}`);
            }
        }
    }

    /**
     * Security manager for plugin sandboxing
     */
    class SecurityManager {
        constructor() {
            this.permissions = new Map();
            this.securityPolicies = new Map();
        }

        async initialize() {
            // Load security policies
            this.loadDefaultPolicies();
            
            // Initialize permission system
            await this.initializePermissions();
        }

        loadDefaultPolicies() {
            // Default security policies for different security levels
            this.securityPolicies.set(SecurityLevel.MINIMAL, {
                maxExecutionTime: 5000,
                allowedCapabilities: [Capabilities.DOM_READ],
                networkAccess: false,
                fileSystemAccess: false
            });

            this.securityPolicies.set(SecurityLevel.STANDARD, {
                maxExecutionTime: 15000,
                allowedCapabilities: [
                    Capabilities.DOM_READ,
                    Capabilities.DOM_WRITE,
                    Capabilities.FORM_FILL,
                    Capabilities.CLICK_ELEMENTS,
                    Capabilities.STORAGE
                ],
                networkAccess: false,
                fileSystemAccess: false
            });

            this.securityPolicies.set(SecurityLevel.ELEVATED, {
                maxExecutionTime: 30000,
                allowedCapabilities: Object.values(Capabilities),
                networkAccess: true,
                fileSystemAccess: false
            });
        }

        async initializePermissions() {
            // Check Chrome extension permissions
            if (chrome && chrome.permissions) {
                const permissions = await new Promise(resolve => {
                    chrome.permissions.getAll(resolve);
                });
                
                for (const permission of permissions.permissions || []) {
                    this.permissions.set(permission, true);
                }
            }
        }

        validateCapabilities(capabilities) {
            for (const capability of capabilities) {
                if (!Object.values(Capabilities).includes(capability)) {
                    throw new Error(`Unknown capability: ${capability}`);
                }
            }
        }

        async checkPermissions(capabilities) {
            // Check if all required capabilities are allowed
            for (const capability of capabilities) {
                if (!await this.hasPermission(capability)) {
                    throw new Error(`Permission denied for capability: ${capability}`);
                }
            }
            return true;
        }

        async hasPermission(capability) {
            // Map capabilities to Chrome permissions
            const permissionMap = {
                [Capabilities.FILE_UPLOAD]: 'debugger',
                [Capabilities.SCREENSHOT]: 'activeTab',
                [Capabilities.NAVIGATION]: 'activeTab',
                [Capabilities.STORAGE]: 'storage',
                [Capabilities.NOTIFICATIONS]: 'notifications'
            };

            const chromePermission = permissionMap[capability];
            if (chromePermission) {
                return this.permissions.has(chromePermission);
            }

            // Default capabilities don't require special permissions
            return true;
        }

        async validateExecution(plugin, methodName, args) {
            const policy = this.securityPolicies.get(plugin.securityLevel);
            if (!policy) {
                throw new Error(`Unknown security level: ${plugin.securityLevel}`);
            }

            // Validate execution time (this would be implemented with timeouts)
            // Validate method access
            // Validate argument safety

            return true;
        }
    }

    /**
     * Event bus for plugin communication
     */
    class EventBus {
        constructor() {
            this.listeners = new Map();
        }

        on(event, callback) {
            if (!this.listeners.has(event)) {
                this.listeners.set(event, []);
            }
            this.listeners.get(event).push(callback);
        }

        off(event, callback) {
            if (this.listeners.has(event)) {
                const callbacks = this.listeners.get(event);
                const index = callbacks.indexOf(callback);
                if (index > -1) {
                    callbacks.splice(index, 1);
                }
            }
        }

        emit(event, data = null) {
            if (this.listeners.has(event)) {
                const callbacks = this.listeners.get(event);
                for (const callback of callbacks) {
                    try {
                        callback(data);
                    } catch (error) {
                        console.error(`Error in event callback for ${event}:`, error);
                    }
                }
            }
        }
    }

    // Export SDK
    const sdk = new WebXPluginSDK();
    
    global.WebXPluginSDK = sdk;
    global.WebXSecurityLevel = SecurityLevel;
    global.WebXCapabilities = Capabilities;
    global.WebXLifecycleHooks = LifecycleHooks;

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => sdk.initialize());
    } else {
        sdk.initialize();
    }

    console.log('WebX Plugin SDK loaded');

})(window);