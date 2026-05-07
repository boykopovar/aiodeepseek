from __future__ import annotations

from .base import _DeepSeekSessionBase
from .chat import _DeepSeekChatMixin
from .files import _DeepSeekFileMixin


class _DeepSeekSession(_DeepSeekSessionBase, _DeepSeekFileMixin, _DeepSeekChatMixin):
    pass

