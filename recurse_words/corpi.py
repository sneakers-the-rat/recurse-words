import typing
import re
from abc import ABC, abstractmethod
from pathlib import Path

import requests

class Corpus(ABC):
    """
    Class to get a corpus
    """

    name = ''
    url = ''
    decode=True
    """decode the raw bytes from the request in download_corpus"""

    def __init__(self, get=False):
        """
        Args:
            get (bool): get the corpus on init
        """
        self._corpus = []
        if get:
            self._corpus = self.get()

    @property
    def corpus(self) -> typing.List[str]:
        if len(self._corpus) == 0:
            self._corpus = self.get()
        return self._corpus

    def download_corpus(self) ->  typing.Union[bytes, str]:
        """Return the raw bytes of the request"""
        res = requests.get(self.url)
        if self.decode:
            return res.content.decode('utf-8', errors='ignore')
        else:
            return res.content

    def get(self) -> typing.List[str]:
        corpus_str = self.download_corpus()
        corpus = self.clean(corpus_str)
        return list(sorted(set(corpus)))

    @abstractmethod
    def clean(self, to_clean:str) -> typing.List[str]:
        """
        Clean the corpus of any debris, returning a list of strings

        Args:
            to_clean (str): the big long string to clean

        Returns:
            list of words
        """
        pass

class Txt(Corpus):

    name = 'txt'

    def __init__(self, path:Path, sep='\n', *args, **kwargs):

        self.url = str(path)
        self.path = path
        self.sep = sep

        super(Txt, self).__init__(*args, **kwargs)

    def download_corpus(self) ->  typing.Union[bytes, str]:
        with open(self.path, 'r') as txtfile:
            corpus_str = txtfile.read()
        return corpus_str

    def clean(self, to_clean:str) -> typing.List[str]:
        return to_clean.split(self.sep)


class English(Corpus):
    name='english'
    url='https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt'

    def clean(self, to_clean:str) -> typing.List[str]:
        return to_clean.split('\r\n')

class CMUDict(Corpus):
    """CMU Phonetic dictionary"""

    name='phonetic'
    url='http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b'


    lut = {
        "AA": "a",
        "AE": "@",
        "AH": "A",
        "AO": "c",
        "AW": "W",
        "AY": "Y",
        "EH": "E",
        "ER": "R",
        "EY": "e",
        "IH": "I",
        "IY": "i",
        "OW": "o",
        "OY": "O",
        "UH": "U",
        "UW": "u",
        "B": "b",
        "CH": "C",
        "D": "d",
        "DH": "D",
        "F": "f",
        "G": "g",
        "HH": "h",
        "JH": "J",
        "K": "k",
        "L": "l",
        "M": "m",
        "N": "n",
        "NG": "G",
        "P": "p",
        "R": "r",
        "S": "s",
        "SH": "S",
        "T": "t",
        "TH": "T",
        "V": "v",
        "W": "w",
        "WH": "H",
        "Y": "y",
        "Z": "z",
        "ZH": "Z"
    }
    """Convert their phonetic code to fingle letters"""

    tul = {v:k for k, v in lut.items()}
    """inverse lookup, single letter to original code"""

    ipa = {
        "a": "ɑ",
        "@": "æ",
        "A": "ʌ",
        "c": "ɔ",
        "W": "aʊ",
        "Y": "aɪ",
        "E": "ɛ",
        "R": "ɝ",
        "e": "eɪ",
        "I": "ɪ",
        "i": "i",
        "o": "oʊ",
        "O": "ɔɪ",
        "U": "ʊ",
        "u": "u",
        "b": "b",
        "C": "tʃ",
        "d": "d",
        "D": "ð",
        "f": "f",
        "g": "ɡ",
        "h": "h",
        "J": "dʒ",
        "k": "k",
        "l": "l",
        "m": "m",
        "n": "n",
        "G": "ŋ",
        "p": "p",
        "r": "ɹ",
        "s": "s",
        "S": "ʃ",
        "t": "t",
        "T": "θ",
        "v": "v",
        "w": "w",
        "H": "ʍ",
        "y": "j",
        "z": "z",
        "Z": "ʒ",
    }
    """lut from single-letter code to IPA symbols"""

    def __init__(self, *args, **kwargs):
        self._phone_to_word = {}

        super(CMUDict, self).__init__(*args, **kwargs)


    def clean(self, to_clean:str) -> typing.List[str]:
        # split into lines and iterate
        corpus = []
        for line in to_clean.split('\n'):
            # ignore the header and the punctuation marks
            if len(line)==0 or not line[0].isalpha():
                continue
            # split into the word and the phonetic symbols,
            word, phones = line.split('  ')

            # translate, stripping numbers (emphasis)
            phones = ''.join([self.lut[re.sub(r'\d+', '', phon)] for phon in phones.split(' ')])

            # store it
            corpus.append(phones)
            self._phone_to_word[phones] = word.lower()
        return corpus





def get_corpus(corp_name:str) -> typing.Type[Corpus]:
    for obj_name, obj in dict(globals()).items():
        try:
            if issubclass(obj, Corpus) and obj.name == corp_name:
                return obj
        except TypeError:
            pass