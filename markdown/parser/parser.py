#!/usr/bin/env python
# coding=utf-8

from markdown.parser.container_parsers import (ContainerElementParser,
                                               BlockQuoteMarkerParser,
                                               ListMarkerParser)
from markdown.parser.container_elements import (BlockQuoteElement,
                                                ListElement)
from markdown.parser.block_parsers import (BlockElementParser,
                                           ParagraphParser,
                                           AtxHeadingParser,
                                           ThematicBreakParser)
from markdown.parser.block_elements import (ParagraphElement,
                                            BlankLineElement,
                                            ThematicBreakElement)
from markdown.parser.inline_parsers import InlineParser
from markdown.parser.inline_elements import TextualContentElement


class Parser(object):
    """The markdown parser."""

    def __init__(self, config=None):
        if config is None:
            config = {}
        config['link_references'] = {}
        config['links'] = []

        self._blocks = []  # The parsed block elements.

        self._interrupt_parsers = []
        self._container_parsers = []
        self._block_parsers = []
        self.init_parsers()

        self._layers = []
        self._line_num = 0

    def parse(self, code):
        """Parse the given code string.

        Args:
            code: an UTF-8 encoded string.

        Returns:
            The parsed elements.
        """
        # Replace insecure characters
        code = code.replace(u'\u0000', u'\uFFFD')
        # Replace line endings with newline (U+000A) character
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        # Add a newline character to the end of code
        if len(code) > 0 and code[-1] != '\n':
            code += '\n'

        lines = code.split('\n')
        for line_num, line in enumerate(lines):
            self._line_num = line_num + 1
            index = self.parse_container_markers(line)
            if not self.parse_continuation(line, index):
                self.parse_blocks(line, index)
        if len(self._blocks) > 0:
            self._blocks[-1].close()

        self._blocks = [self.parse_subs(block) for block in self._blocks]
        return self._blocks

    def init_parsers(self):
        self._interrupt_parsers = [
            ThematicBreakParser,
            AtxHeadingParser,
            # FencedCodeBlockParser(config),
            # HtmlBlockParser(config)  # Type 1-6,
        ]
        self._container_parsers = [
            ThematicBreakParser,
            BlockQuoteMarkerParser,
            ListMarkerParser,
        ]
        self._block_parsers = [
            ThematicBreakParser,
            AtxHeadingParser,
            ParagraphParser,
        ]

    def parse_container_markers(self, line):
        index = 0
        layer_index = 0
        while False:
            elem, index = BlockQuoteMarkerParser.parse(line, index)
            if isinstance(elem, ThematicBreakElement):
                elem.line_num = self._line_num
                self._blocks.append(elem)
                return len(line)
            if not elem:
                offset = 0
                if layer_index < len(self._layers) and \
                        isinstance(self._layers[layer_index], BlockQuoteElement):
                    offset = self._layers[layer_index].offset()
                elem, index = ListMarkerParser.parse(line, index, {
                    ContainerElementParser.AUX_ALIGN: offset
                })
                if not elem:
                    break
        return index

    def parse_continuation(self, line, index):
        """Continue parsing block elements that could span multiple lines.

        Args:
            line: line of code.
            index: start index

        Returns:
            Returns true if succeed, otherwise false.
        """
        if len(self._blocks) > 0 and not self._blocks[-1].closed:
            if isinstance(self._blocks[-1], ParagraphElement):
                has_interrupted = False
                for interrupt_parser in self._interrupt_parsers:
                    elem = interrupt_parser.parse(line, index, {
                        BlockElementParser.AUX_INTERRUPT: True
                    })
                    if elem is not None:
                        has_interrupted = True
                        self._blocks[-1].close()
                        elem.line_num = self._line_num
                        self._blocks.append(elem)
                        break
                if not has_interrupted:
                    self._blocks[-1] = ParagraphParser.parse(line, index, {
                        BlockElementParser.AUX_UNCLOSED: self._blocks[-1]
                    })
            return True
        return False

    def parse_blocks(self, line, index):
        """Parse block elements.

        Args:
            line: line of code.
            index: start index

        Returns:
            None
        """
        for block_parser in self._block_parsers:
            elem = block_parser.parse(line, index)
            if elem is not None:
                if isinstance(elem, BlankLineElement):
                    break
                elem.line_num = self._line_num
                self._blocks.append(elem)
                break

    def parse_subs(self, elem):
        """Parse span elements recursively.

        Args:
            elem: the elements that contain sub-elements.

        Returns:
            The parsed element.
        """
        if isinstance(elem, TextualContentElement):
            return elem
        try:
            for i, sub in enumerate(elem.subs):
                elem.subs[i] = self.parse_subs(InlineParser.parse(sub))
        except AttributeError:
            pass
        return elem
