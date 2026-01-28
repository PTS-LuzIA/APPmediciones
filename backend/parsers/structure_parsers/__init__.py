"""
Structure Parsers - Parsers especializados para extraer jerarquía (FASE 1)
"""
from .structure_parser_base import StructureParserBase
from .structure_parser_explicit import StructureParserExplicit
from .structure_parser_implicit import StructureParserImplicit

__all__ = [
    'StructureParserBase',
    'StructureParserExplicit',
    'StructureParserImplicit'
]
