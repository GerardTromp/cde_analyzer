"""
Vocabulary class for phrase_miner action.

Provides bidirectional token-to-ID mapping for efficient k-mer processing.
"""

from typing import Dict, List


class Vocabulary:
    """Bidirectional token-to-ID mapping for k-mer phrase mining"""

    def __init__(self):
        self.tok2id: Dict[str, int] = {}
        self.id2tok: Dict[int, str] = {}

    def add_token(self, token: str) -> int:
        """
        Add token and return its ID (or existing ID if already present).

        Args:
            token: Token string to add to vocabulary

        Returns:
            Integer ID for the token
        """
        if token not in self.tok2id:
            new_id = len(self.tok2id)
            self.tok2id[token] = new_id
            self.id2tok[new_id] = token
            return new_id
        return self.tok2id[token]

    def get_token(self, token_id: int) -> str:
        """
        Get token string from ID.

        Args:
            token_id: Integer ID

        Returns:
            Token string

        Raises:
            KeyError: If token_id not in vocabulary
        """
        return self.id2tok[token_id]

    def get_tokens(self, ids: List[int]) -> List[str]:
        """
        Convert list of token IDs to token strings.

        Args:
            ids: List of integer IDs

        Returns:
            List of token strings
        """
        return [self.id2tok[i] for i in ids]

    def __len__(self) -> int:
        """Return vocabulary size"""
        return len(self.tok2id)

    def __contains__(self, token: str) -> bool:
        """Check if token is in vocabulary"""
        return token in self.tok2id
