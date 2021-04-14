import typing
import re
from abc import ABC, abstractmethod
from pathlib import Path
import gzip
import io
import pickle
import pdb

import requests

class Corpus(ABC):
    """
    Class to get a corpus
    """

    name = ''
    url = ''
    decode=True
    """decode the raw bytes from the request in download_corpus"""

    def __init__(self, get=False, cache_dir='~/.recurse_words'):
        """
        Args:
            get (bool): get the corpus on init
        """
        self._retranslate_lut = {}
        self._retranslate_tul = {}
        self._corpus = []
        self._corpus_dict = {}
        self.cache_dir = Path(cache_dir).expanduser().absolute()
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        self.cache_file = (self.cache_dir / self.name).with_suffix('.pck')
        if get:
            self._corpus = self.get()

    @property
    def corpus(self) -> typing.List[str]:
        if len(self._corpus) == 0:
            self._corpus = self.get()
        return self._corpus

    @property
    def corpus_dict(self) -> typing.Dict[str, int]:
        if len(self._corpus_dict) == 0:
            self._corpus_dict = {k:1 for k in self.corpus}
        return self._corpus_dict

    def download_corpus(self) ->  typing.Union[bytes, str]:
        """Return the raw bytes of the request"""
        res = requests.get(self.url)
        if self.decode:
            return res.content.decode('utf-8', errors='ignore')
        else:
            return res.content

    def _load(self) -> typing.List[str]:
        with open(self.cache_file, 'rb') as cache_file:
            corpus = pickle.load(cache_file)
        return corpus

    def _save(self, corpus:typing.List[str]):
        with open(self.cache_file, 'wb') as cache_file:
            pickle.dump(corpus, cache_file)

    def get(self) -> typing.List[str]:
        if self.cache_file.exists():
            print(f'Loading cached corpus from {self.cache_file}')
            corpus = self._load()
        else:
            print("Downloading corpus")
            corpus_str = self.download_corpus()
            corpus = self.clean(corpus_str)
            corpus = list(sorted(set(corpus)))
            self._save(corpus)
        return corpus

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

class Common_English(Corpus):
    name='common'
    url='https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa.txt'

    def __init__(self, nth_most:int = 10000, *args, **kwargs):
        """
        Args:
            nth_most (int): only get the nth most common words, default 10000 (the whole list)
        """
        super(Common_English, self).__init__(*args, **kwargs)
        self.nth_most = nth_most

    def clean(self, to_clean:str) -> typing.List[str]:
        corpus = to_clean.split('\n')
        return corpus[0:self.nth_most]

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
            self._retranslate_lut[phones] = word.lower()
            self._retranslate_tul[word.lower()] = phones
        return corpus

class CMUDict_Common(CMUDict):
    name='phonetic_common'

    def __init__(self, nth_most = 10000, *args, **kwargs):
        super(CMUDict_Common, self).__init__(*args, **kwargs)
        self.nth_most = nth_most
        self._common = Common_English(nth_most=self.nth_most)

    def clean(self, to_clean:str) -> typing.List[str]:
        # split into lines and iterate
        corpus = []
        for line in to_clean.split('\n'):
            # ignore the header and the punctuation marks
            if len(line)==0 or not line[0].isalpha():
                continue
            # split into the word and the phonetic symbols,
            word, phones = line.split('  ')

            if word.lower() not in self._common.corpus_dict.keys():
                continue

            # translate, stripping numbers (emphasis)
            phones = ''.join([self.lut[re.sub(r'\d+', '', phon)] for phon in phones.split(' ')])

            # store it
            corpus.append(phones)
            self._retranslate_lut[phones] = word.lower()
            self._retranslate_tul[word.lower()] = phones
        return corpus




class Proteins(Corpus):
    name = 'proteins'
    url = 'https://ftp.ncbi.nih.gov/genomes/refseq/vertebrate_mammalian/Homo_sapiens/latest_assembly_versions/GCF_000001405.39_GRCh38.p13/GCF_000001405.39_GRCh38.p13_protein.faa.gz'
    decode = False

    def clean(self, to_clean:bytes) -> typing.List[str]:
        # un-gzip
        lines = []
        sublines = []
        protein_name = None
        with gzip.GzipFile(fileobj=io.BytesIO(to_clean)) as gfile:
            for row in gfile.readlines():
                row = row.decode('utf-8').rstrip('\n')
                if row.startswith('>'):
                    if protein_name is not None:
                        protein_code = ''.join(sublines)
                        self._retranslate_lut[protein_code] = protein_name
                        lines.append(protein_code)
                        sublines = []
                    protein_name = row
                else:
                    sublines.append(row)

            # handle end case like an animal
            protein_code = ''.join(sublines)
            self._retranslate_lut[protein_code] = protein_name
            lines.append(protein_code)

        return lines


def get_corpus(corp_name:str) -> typing.Type[Corpus]:
    for obj_name, obj in dict(globals()).items():
        try:
            if issubclass(obj, Corpus) and obj.name == corp_name:
                return obj
        except TypeError:
            pass