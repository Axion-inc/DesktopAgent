/**
 * WebX Form Helper Plugin
 * Example plugin demonstrating WebX SDK capabilities
 * 
 * This plugin provides enhanced form automation capabilities
 * including smart field detection and validation.
 */

(async function() {
    'use strict';

    // Wait for SDK to be available
    while (!window.WebXPluginSDK) {
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    const { WebXPluginSDK, WebXCapabilities, WebXLifecycleHooks } = window;

    // Plugin configuration
    const pluginConfig = {
        id: 'form-helper',
        name: 'Smart Form Helper',
        version: '1.0.0',
        description: 'Enhanced form automation with smart field detection and validation',
        author: 'Desktop Agent Team',
        
        capabilities: [
            WebXCapabilities.DOM_READ,
            WebXCapabilities.DOM_WRITE,
            WebXCapabilities.FORM_FILL,
            WebXCapabilities.CLICK_ELEMENTS,
            WebXCapabilities.STORAGE
        ],

        securityLevel: window.WebXSecurityLevel.STANDARD,

        // Plugin configuration
        config: {
            autoValidation: true,
            smartFieldMatching: true,
            saveFormData: false
        },

        // Plugin initialization
        async init() {
            console.log('Form Helper Plugin initializing...');
            
            // Load saved configuration
            const savedConfig = await this.getStorage('config');
            if (savedConfig) {
                Object.assign(this.config, savedConfig);
            }

            // Initialize form detection patterns
            this.initializeFormPatterns();
        },

        // Plugin activation
        async activate() {
            console.log('Form Helper Plugin activated');
            
            // Set up form observation
            this.observeForms();
            
            // Register custom form commands
            this.registerFormCommands();
        },

        // Plugin deactivation
        async deactivate() {
            console.log('Form Helper Plugin deactivated');
            
            // Clean up observers
            if (this.formObserver) {
                this.formObserver.disconnect();
            }
        },

        // Custom plugin methods
        methods: {
            /**
             * Initialize form field patterns for smart matching
             */
            initializeFormPatterns() {
                this.fieldPatterns = {
                    // Japanese patterns
                    name: ['氏名', '名前', 'お名前', 'ネーム', 'なまえ'],
                    email: ['メール', 'Eメール', 'メールアドレス', '電子メール'],
                    phone: ['電話番号', 'TEL', '電話', '携帯番号', '携帯電話'],
                    address: ['住所', 'ご住所', 'じゅうしょ'],
                    company: ['会社名', '勤務先', '企業名', '会社'],
                    
                    // English patterns
                    firstName: ['first name', 'given name', 'firstname'],
                    lastName: ['last name', 'family name', 'surname', 'lastname'],
                    password: ['password', 'passwd', 'pwd'],
                    confirmPassword: ['confirm password', 'password confirmation', 'retype password']
                };

                this.inputTypeMapping = {
                    email: 'email',
                    phone: 'tel',
                    password: 'password',
                    confirmPassword: 'password'
                };
            },

            /**
             * Observe forms on the page for dynamic content
             */
            observeForms() {
                // Create mutation observer for dynamic forms
                this.formObserver = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        mutation.addedNodes.forEach((node) => {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                // Check for new forms
                                if (node.tagName === 'FORM' || node.querySelector('form')) {
                                    this.analyzeForm(node.tagName === 'FORM' ? node : node.querySelector('form'));
                                }
                            }
                        });
                    });
                });

                // Start observing
                this.formObserver.observe(document.body, {
                    childList: true,
                    subtree: true
                });

                // Analyze existing forms
                document.querySelectorAll('form').forEach(form => this.analyzeForm(form));
            },

            /**
             * Analyze form structure and add metadata
             */
            analyzeForm(form) {
                if (!form || form.hasAttribute('data-webx-analyzed')) return;

                console.log('Analyzing form:', form);

                // Mark as analyzed
                form.setAttribute('data-webx-analyzed', 'true');

                // Analyze form fields
                const formData = {
                    id: form.id || 'unnamed-form',
                    fields: [],
                    submitButtons: [],
                    resetButtons: []
                };

                // Find all form inputs
                const inputs = form.querySelectorAll('input, select, textarea');
                inputs.forEach((input, index) => {
                    const fieldData = this.analyzeFormField(input, index);
                    if (fieldData) {
                        formData.fields.push(fieldData);
                    }
                });

                // Find submit and reset buttons
                form.querySelectorAll('button, input[type="submit"], input[type="reset"]').forEach(button => {
                    const type = button.type || 'button';
                    if (type === 'submit') {
                        formData.submitButtons.push({
                            element: button,
                            text: button.textContent || button.value || 'Submit'
                        });
                    } else if (type === 'reset') {
                        formData.resetButtons.push({
                            element: button,
                            text: button.textContent || button.value || 'Reset'
                        });
                    }
                });

                // Store form analysis
                form._webxFormData = formData;

                // Emit form analyzed event
                this.emit('form:analyzed', { form, data: formData });
            },

            /**
             * Analyze individual form field
             */
            analyzeFormField(input, index) {
                const fieldData = {
                    element: input,
                    index: index,
                    type: input.type || 'text',
                    name: input.name || '',
                    id: input.id || '',
                    placeholder: input.placeholder || '',
                    required: input.required,
                    labels: [],
                    suggestedFieldType: null
                };

                // Find associated labels
                this.findFieldLabels(input, fieldData);

                // Determine field type from labels and attributes
                fieldData.suggestedFieldType = this.suggestFieldType(fieldData);

                return fieldData;
            },

            /**
             * Find labels associated with form field
             */
            findFieldLabels(input, fieldData) {
                // Find label by 'for' attribute
                if (input.id) {
                    const labelForId = document.querySelector(`label[for="${input.id}"]`);
                    if (labelForId) {
                        fieldData.labels.push({
                            type: 'for',
                            text: labelForId.textContent.trim(),
                            element: labelForId
                        });
                    }
                }

                // Find parent label
                const parentLabel = input.closest('label');
                if (parentLabel) {
                    fieldData.labels.push({
                        type: 'parent',
                        text: parentLabel.textContent.trim(),
                        element: parentLabel
                    });
                }

                // Find nearby labels (previous siblings, etc.)
                const prevSibling = input.previousElementSibling;
                if (prevSibling && (prevSibling.tagName === 'LABEL' || prevSibling.textContent.trim())) {
                    fieldData.labels.push({
                        type: 'previous',
                        text: prevSibling.textContent.trim(),
                        element: prevSibling
                    });
                }

                // Check for aria-label
                if (input.getAttribute('aria-label')) {
                    fieldData.labels.push({
                        type: 'aria-label',
                        text: input.getAttribute('aria-label'),
                        element: null
                    });
                }
            },

            /**
             * Suggest field type based on labels and attributes
             */
            suggestFieldType(fieldData) {
                const allText = [
                    fieldData.name,
                    fieldData.id,
                    fieldData.placeholder,
                    ...fieldData.labels.map(l => l.text)
                ].join(' ').toLowerCase();

                // Check against patterns
                for (const [fieldType, patterns] of Object.entries(this.fieldPatterns)) {
                    for (const pattern of patterns) {
                        if (allText.includes(pattern.toLowerCase())) {
                            return fieldType;
                        }
                    }
                }

                // Fallback to input type
                return fieldData.type;
            },

            /**
             * Register custom form commands
             */
            registerFormCommands() {
                // Listen for form fill commands
                this.sdk.eventBus.on('webx:fill_smart_form', async (data) => {
                    await this.fillSmartForm(data.formData, data.options);
                });

                this.sdk.eventBus.on('webx:validate_form', async (data) => {
                    await this.validateForm(data.formSelector);
                });
            },

            /**
             * Smart form filling using field type suggestions
             */
            async fillSmartForm(formData, options = {}) {
                console.log('Smart form fill requested:', formData);

                const results = [];

                for (const [fieldKey, value] of Object.entries(formData)) {
                    try {
                        const field = await this.findBestMatchingField(fieldKey);
                        if (field) {
                            await this.fillField(field, value);
                            results.push({ 
                                field: fieldKey, 
                                success: true, 
                                element: field.element 
                            });
                        } else {
                            results.push({ 
                                field: fieldKey, 
                                success: false, 
                                error: 'Field not found' 
                            });
                        }
                    } catch (error) {
                        results.push({ 
                            field: fieldKey, 
                            success: false, 
                            error: error.message 
                        });
                    }
                }

                // Auto-validate if enabled
                if (this.config.autoValidation && options.validate !== false) {
                    await this.validateCurrentForm();
                }

                return results;
            },

            /**
             * Find best matching field for given field key
             */
            async findBestMatchingField(fieldKey) {
                // Get all analyzed forms
                const forms = document.querySelectorAll('form[data-webx-analyzed]');
                
                let bestMatch = null;
                let bestScore = 0;

                for (const form of forms) {
                    const formData = form._webxFormData;
                    if (!formData) continue;

                    for (const field of formData.fields) {
                        const score = this.calculateFieldMatchScore(fieldKey, field);
                        if (score > bestScore) {
                            bestScore = score;
                            bestMatch = field;
                        }
                    }
                }

                return bestMatch;
            },

            /**
             * Calculate match score between field key and form field
             */
            calculateFieldMatchScore(fieldKey, field) {
                let score = 0;

                // Exact matches
                if (field.suggestedFieldType === fieldKey) score += 100;
                if (field.name === fieldKey) score += 80;
                if (field.id === fieldKey) score += 70;

                // Pattern matches in labels
                const patterns = this.fieldPatterns[fieldKey] || [fieldKey];
                for (const pattern of patterns) {
                    for (const label of field.labels) {
                        if (label.text.toLowerCase().includes(pattern.toLowerCase())) {
                            score += 50;
                            break;
                        }
                    }
                }

                // Partial matches
                if (field.name.includes(fieldKey) || fieldKey.includes(field.name)) {
                    score += 30;
                }

                if (field.placeholder.toLowerCase().includes(fieldKey.toLowerCase())) {
                    score += 20;
                }

                return score;
            },

            /**
             * Fill individual field with validation
             */
            async fillField(field, value) {
                const element = field.element;

                // Pre-fill validation
                if (field.type === 'email' && !this.isValidEmail(value)) {
                    throw new Error(`Invalid email format: ${value}`);
                }

                // Focus element
                element.focus();

                // Clear existing value
                element.value = '';

                // Set new value
                if (element.tagName === 'SELECT') {
                    // Handle select elements
                    const option = Array.from(element.options).find(opt => 
                        opt.value === value || opt.textContent.includes(value)
                    );
                    if (option) {
                        element.value = option.value;
                    } else {
                        throw new Error(`Option not found in select: ${value}`);
                    }
                } else {
                    // Handle input/textarea
                    element.value = value;
                }

                // Trigger events
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));

                // Visual feedback
                element.style.borderColor = '#28a745';
                setTimeout(() => {
                    element.style.borderColor = '';
                }, 1000);
            },

            /**
             * Validate current form
             */
            async validateCurrentForm() {
                const activeForm = document.activeElement?.closest('form');
                if (!activeForm) return { valid: true, errors: [] };

                return await this.validateForm(activeForm);
            },

            /**
             * Validate specific form
             */
            async validateForm(form) {
                if (typeof form === 'string') {
                    form = document.querySelector(form);
                }

                if (!form) {
                    throw new Error('Form not found for validation');
                }

                const formData = form._webxFormData;
                const errors = [];

                if (formData) {
                    for (const field of formData.fields) {
                        const element = field.element;
                        const value = element.value.trim();

                        // Required field validation
                        if (field.required && !value) {
                            errors.push({
                                field: field,
                                error: 'Required field is empty',
                                element: element
                            });
                        }

                        // Type-specific validation
                        if (value && field.suggestedFieldType === 'email' && !this.isValidEmail(value)) {
                            errors.push({
                                field: field,
                                error: 'Invalid email format',
                                element: element
                            });
                        }

                        if (value && field.suggestedFieldType === 'phone' && !this.isValidPhone(value)) {
                            errors.push({
                                field: field,
                                error: 'Invalid phone format',
                                element: element
                            });
                        }
                    }
                }

                // Visual feedback for errors
                errors.forEach(error => {
                    error.element.style.borderColor = '#dc3545';
                });

                return { valid: errors.length === 0, errors };
            },

            /**
             * Email validation
             */
            isValidEmail(email) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                return emailRegex.test(email);
            },

            /**
             * Phone validation (supports Japanese and international formats)
             */
            isValidPhone(phone) {
                // Japanese phone formats
                const japanesePhone = /^(\+81|0)[0-9-\s()]{8,}$/;
                // International format
                const internationalPhone = /^\+[1-9]\d{1,14}$/;
                // US format
                const usPhone = /^\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$/;

                return japanesePhone.test(phone) || internationalPhone.test(phone) || usPhone.test(phone);
            },

            /**
             * Export form analysis for debugging
             */
            exportFormAnalysis() {
                const forms = document.querySelectorAll('form[data-webx-analyzed]');
                const analysis = [];

                forms.forEach((form, index) => {
                    const formData = form._webxFormData;
                    if (formData) {
                        analysis.push({
                            formIndex: index,
                            formId: formData.id,
                            fieldsCount: formData.fields.length,
                            fields: formData.fields.map(f => ({
                                type: f.type,
                                name: f.name,
                                id: f.id,
                                suggestedFieldType: f.suggestedFieldType,
                                labels: f.labels.map(l => ({ type: l.type, text: l.text }))
                            })),
                            submitButtons: formData.submitButtons.map(b => b.text)
                        });
                    }
                });

                console.table(analysis);
                return analysis;
            }
        }
    };

    // Register the plugin
    try {
        const plugin = WebXPluginSDK.registerPlugin(pluginConfig);
        await plugin.activate();
        
        console.log('Form Helper Plugin loaded and activated successfully');

        // Expose plugin for debugging
        window.FormHelperPlugin = plugin;

    } catch (error) {
        console.error('Failed to load Form Helper Plugin:', error);
    }

})();