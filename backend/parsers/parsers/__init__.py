"""
Parsers especializados por tipo de documento
"""

from .base_parser import BaseParserV2
from .tipo1_inline_simple import ParserV2_Tipo1_InlineSimple

__all__ = [
    'BaseParserV2',
    'ParserV2_Tipo1_InlineSimple',
]
