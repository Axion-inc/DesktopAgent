from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


class IntentMatcher:
    """Rule-based natural language intent matching for DSL generation."""

    def __init__(self):
        # Pattern definitions for different intents
        self.patterns = {
            # File operations
            'file_find': [
                r'find\s+.*files?',
                r'search\s+.*files?',
                r'ファイル.*探',
                r'ファイル.*検索',
                r'.*pdf.*探',
                r'.*pdf.*find',
                r'.*pdf.*files',
                r'move.*pdf.*files',
                r'pdf.*backup'
            ],
            'file_move': [
                r'move\s+.*files?',
                r'copy\s+.*files?',
                r'ファイル.*移動',
                r'ファイル.*コピー',
                r'.*移動.*フォルダ',
                r'organize.*files?',
                r'.*整理.*ファイル',
                r'ファイル.*整理',
                r'.*整理.*フォルダ',
                r'downloads.*folder',
                r'ダウンロード.*フォルダ'
            ],
            'pdf_merge': [
                r'merge\s+.*pdf',
                r'combine\s+.*pdf',
                r'pdf.*merge',
                r'pdf.*結合',
                r'pdf.*まとめ',
                r'.*結合.*pdf'
            ],

            # Web operations
            'web_form': [
                r'fill\s+.*form',
                r'submit\s+.*form',
                r'フォーム.*入力',
                r'フォーム.*送信',
                r'.*入力.*web',
                r'.*送信.*web',
                r'csv.*form',
                r'csv.*フォーム'
            ],
            'web_click': [
                r'click\s+.*button',
                r'press\s+.*button',
                r'ボタン.*クリック',
                r'ボタン.*押',
                r'.*クリック.*ボタン'
            ],

            # Email operations
            'email_compose': [
                r'send\s+.*email',
                r'compose\s+.*mail',
                r'メール.*送信',
                r'メール.*作成',
                r'.*送信.*メール'
            ],
            'email_attach': [
                r'attach\s+.*file',
                r'添付.*ファイル',
                r'ファイル.*添付'
            ],

            # Data operations
            'csv_process': [
                r'csv.*process',
                r'process.*csv',
                r'csv.*読',
                r'csv.*処理',
                r'.*処理.*csv',
                r'csv.*file',
                r'csvファイル',
                r'.*csv.*data',
                r'csvから',
                r'csv.*転記'
            ]
        }

        # Template mappings
        self.templates = {
            'pdf_merge_email': 'weekly_report.yaml',
            'csv_to_form': 'csv_to_form.yaml',
            'file_organization': 'downloads_tidy.yaml'
        }

    def analyze_intent(self, text: str) -> Dict[str, Any]:
        """Analyze natural language text and extract intent."""
        text_lower = text.lower()
        matched_intents = []

        # Check each pattern category
        for intent_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched_intents.append(intent_type)
                    break

        # Extract entities (simple keyword extraction)
        entities = self._extract_entities(text_lower)

        # Determine primary intent
        primary_intent = self._determine_primary_intent(matched_intents, entities)

        return {
            'text': text,
            'matched_intents': matched_intents,
            'primary_intent': primary_intent,
            'entities': entities,
            'confidence': self._calculate_confidence(matched_intents, entities)
        }

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text."""
        entities = {
            'file_types': [],
            'locations': [],
            'actions': [],
            'quantities': []
        }

        # File types
        file_patterns = [
            r'pdf', r'csv', r'txt', r'doc', r'excel', r'image'
        ]
        for pattern in file_patterns:
            if re.search(pattern, text):
                entities['file_types'].append(pattern)

        # Common locations
        location_patterns = [
            r'desktop', r'download', r'folder', r'directory',
            r'デスクトップ', r'ダウンロード', r'フォルダ'
        ]
        for pattern in location_patterns:
            if re.search(pattern, text):
                entities['locations'].append(pattern)

        # Actions
        action_patterns = [
            r'send', r'submit', r'merge', r'combine', r'move', r'copy',
            r'送信', r'結合', r'移動', r'コピー'
        ]
        for pattern in action_patterns:
            if re.search(pattern, text):
                entities['actions'].append(pattern)

        # Quantities (simple number extraction)
        numbers = re.findall(r'\d+', text)
        entities['quantities'] = numbers

        return entities

    def _determine_primary_intent(self, intents: List[str], entities: Dict[str, Any]) -> str:
        """Determine the primary intent based on matched patterns and entities."""
        if not intents:
            return 'unknown'

        # Priority rules
        if 'csv_process' in intents and 'web_form' in intents:
            return 'csv_to_form'
        elif 'pdf_merge' in intents and 'email_compose' in intents:
            return 'pdf_merge_email'
        elif 'file_find' in intents and 'file_move' in intents:
            return 'file_organization'
        elif len(intents) == 1:
            return intents[0]
        else:
            # Return the first matched intent
            return intents[0]

    def _calculate_confidence(self, intents: List[str], entities: Dict[str, Any]) -> float:
        """Calculate confidence score for the intent analysis."""
        if not intents:
            return 0.0

        # Base confidence from number of matched intents
        base_confidence = min(0.8, len(intents) * 0.3)

        # Boost from entities
        entity_boost = min(0.2, sum(len(v) for v in entities.values()) * 0.05)

        return min(1.0, base_confidence + entity_boost)


class DSLGenerator:
    """Generates DSL plans from analyzed intents."""

    def __init__(self):
        self.intent_matcher = IntentMatcher()

    def generate_plan(self, intent_text: str) -> Dict[str, Any]:
        """Generate a DSL plan from natural language intent."""
        # Analyze intent
        analysis = self.intent_matcher.analyze_intent(intent_text)

        # Generate plan based on primary intent
        primary_intent = analysis['primary_intent']

        if primary_intent == 'csv_to_form':
            plan = self._generate_csv_to_form_plan(analysis)
        elif primary_intent == 'pdf_merge_email':
            plan = self._generate_pdf_merge_email_plan(analysis)
        elif primary_intent == 'file_organization':
            plan = self._generate_file_organization_plan(analysis)
        elif primary_intent == 'web_form':
            plan = self._generate_web_form_plan(analysis)
        elif primary_intent == 'file_find':
            plan = self._generate_file_find_plan(analysis)
        else:
            plan = self._generate_generic_plan(analysis)

        # Add metadata
        plan['_generated'] = True
        plan['_source_intent'] = intent_text
        plan['_analysis'] = analysis
        plan['_confidence'] = analysis['confidence']

        return plan

    def _generate_csv_to_form_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate CSV to form submission plan."""
        return {
            'dsl_version': '1.1',
            'name': 'CSV → フォーム転記（生成済み）',
            'description': f'Generated from: "{analysis["text"]}"',
            'variables': {
                'csv_file': 'sample_data/contacts.csv',
                'form_url': 'http://localhost:8000/mock/form',
                'max_records': 3
            },
            'steps': [
                {
                    'find_files': {
                        'query': '{{csv_file}}',
                        'roots': ['./'],
                        'limit': 1
                    }
                },
                {
                    'open_browser': {
                        'url': '{{form_url}}',
                        'context': 'form_session',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '氏名',
                        'text': 'テスト太郎',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'fill_by_label': {
                        'label': 'メール',
                        'text': 'test@example.com',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '件名',
                        'text': '自動生成テスト',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '本文',
                        'text': 'これは自動生成されたテストメッセージです。',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'click_by_text': {
                        'text': '送信',
                        'role': 'button',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'log': {
                        'message': 'CSV to form transfer completed',
                        'when': '{{steps[0].found}} > 0'
                    }
                }
            ]
        }

    def _generate_pdf_merge_email_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF merge and email plan."""
        return {
            'dsl_version': '1.1',
            'name': 'PDF結合 & メール送信（生成済み）',
            'description': f'Generated from: "{analysis["text"]}"',
            'variables': {
                'inbox': './sample_data',
                'workdir': './data/work',
                'out_pdf': './data/weekly_merged.pdf'
            },
            'steps': [
                {
                    'find_files': {
                        'query': 'kind:pdf',
                        'roots': ['{{inbox}}'],
                        'limit': 10
                    }
                },
                {
                    'pdf_merge': {
                        'inputs_from': '{{inbox}}',
                        'out': '{{out_pdf}}',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'compose_mail': {
                        'to': ['test@example.com'],
                        'subject': '結合済みPDFファイル',
                        'body': '自動生成されたPDFファイルを添付します。',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'attach_files': {
                        'paths': ['{{out_pdf}}'],
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'save_draft': {
                        'when': '{{steps[0].found}} > 0'
                    }
                }
            ]
        }

    def _generate_file_organization_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate file organization plan."""
        return {
            'dsl_version': '1.1',
            'name': 'ファイル整理（生成済み）',
            'description': f'Generated from: "{analysis["text"]}"',
            'variables': {
                'source_dir': './data',
                'dest_dir': './data/organized'
            },
            'steps': [
                {
                    'find_files': {
                        'query': 'kind:pdf',
                        'roots': ['{{source_dir}}'],
                        'limit': 50
                    }
                },
                {
                    'move_to': {
                        'dest': '{{dest_dir}}/pdfs',
                        'when': '{{steps[0].found}} > 0'
                    }
                },
                {
                    'log': {
                        'message': 'File organization completed. Moved {{steps[1].moved}} files.',
                        'when': '{{steps[0].found}} > 0'
                    }
                }
            ]
        }

    def _generate_web_form_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate simple web form plan."""
        return {
            'dsl_version': '1.1',
            'name': 'Webフォーム操作（生成済み）',
            'description': f'Generated from: "{analysis["text"]}"',
            'variables': {
                'form_url': 'http://localhost:8000/mock/form'
            },
            'steps': [
                {
                    'open_browser': {
                        'url': '{{form_url}}'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '氏名',
                        'text': 'サンプル太郎'
                    }
                },
                {
                    'fill_by_label': {
                        'label': 'メール',
                        'text': 'sample@example.com'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '件名',
                        'text': 'テスト件名'
                    }
                },
                {
                    'fill_by_label': {
                        'label': '本文',
                        'text': 'これはテストメッセージです。'
                    }
                }
            ]
        }

    def _generate_file_find_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate file search plan."""
        file_types = analysis['entities'].get('file_types', ['pdf'])
        file_type = file_types[0] if file_types else 'pdf'

        return {
            'dsl_version': '1.1',
            'name': f'{file_type.upper()}ファイル検索（生成済み）',
            'description': f'Generated from: "{analysis["text"]}"',
            'variables': {
                'search_dir': './data',
                'file_type': file_type
            },
            'steps': [
                {
                    'find_files': {
                        'query': f'kind:{file_type}',
                        'roots': ['{{search_dir}}'],
                        'limit': 20
                    }
                },
                {
                    'log': {
                        'message': 'Found {{steps[0].found}} {{file_type}} files in {{search_dir}}'
                    }
                }
            ]
        }

    def _generate_generic_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a generic plan for unknown intents."""
        return {
            'dsl_version': '1.1',
            'name': '汎用プラン（生成済み）',
            'description': f'Generated from: "{analysis["text"]}" - Intent: {analysis["primary_intent"]}',
            'variables': {},
            'steps': [
                {
                    'log': {
                        'message': f'Processing request: {analysis["text"]}'
                    }
                },
                {
                    'log': {
                        'message': (
                            f'Detected intent: {analysis["primary_intent"]} '
                            f'(confidence: {analysis["confidence"]:.2f})'
                        )
                    }
                }
            ]
        }


class PlannerL1:
    """Level 1 Planner - Template-based DSL generation from natural language."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.generator = DSLGenerator()

    def generate_plan_from_intent(self, intent_text: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Generate a DSL plan from natural language intent.

        Returns:
            Tuple of (success, plan_dict, message)
        """
        if not self.enabled:
            return False, {}, "Planner L1 is disabled. Set features.llm.enabled=true to enable."

        if not intent_text or not intent_text.strip():
            return False, {}, "Empty intent text provided."

        try:
            plan = self.generator.generate_plan(intent_text)

            confidence = plan.get('_confidence', 0.0)
            if confidence < 0.3:
                return False, plan, f"Low confidence ({confidence:.2f}) in intent analysis. Please be more specific."

            message = f"Generated plan with {confidence:.0%} confidence. Review and edit before execution."
            return True, plan, message

        except Exception as e:
            return False, {}, f"Error generating plan: {str(e)}"

    def is_enabled(self) -> bool:
        """Check if Planner L1 is enabled."""
        return self.enabled

    def set_enabled(self, enabled: bool):
        """Enable or disable Planner L1."""
        self.enabled = enabled


# Global planner instance
planner_l1 = PlannerL1(enabled=False)  # Default OFF


def generate_plan_from_intent(intent_text: str) -> Tuple[bool, Dict[str, Any], str]:
    """Convenience function to generate plan from intent."""
    return planner_l1.generate_plan_from_intent(intent_text)


def is_planner_enabled() -> bool:
    """Check if planner is enabled."""
    return planner_l1.is_enabled()


def set_planner_enabled(enabled: bool):
    """Enable or disable planner."""
    planner_l1.set_enabled(enabled)
