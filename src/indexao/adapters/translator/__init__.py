"""Translator adapter module."""

from indexao.adapters.translator.base import TranslatorAdapter, TranslationResult
from indexao.adapters.translator.mock import MockTranslatorAdapter

__all__ = ['TranslatorAdapter', 'TranslationResult', 'MockTranslatorAdapter']
