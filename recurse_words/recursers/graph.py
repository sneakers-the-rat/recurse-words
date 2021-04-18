import multiprocessing as mp
from itertools import repeat
import pickle
from pathlib import Path
import typing

from tqdm import tqdm
import pygraphviz as pgv
import networkx as nx

from recurse_words.corpi import get_corpus
from recurse_words.recursers.recurser import Recurser

class Graph_Recurser(Recurser):
    """
    Turns out its a aa a lll a grappp hhh maaaaeeeennnnnn

    This class will eventually replace :class:`.Recurser` as there's no reason to have both I
    just didn't want to screw that one up is all.

    """
    def __init__(self, corpus, subtractions:bool=True, replacements:bool=True, *args, **kwargs):
        """

        Args:
            corpus ():
            subtractions ():
            replacements ():
            *args ():
            **kwargs ():
        """
        super(Graph_Recurser, self).__init__(corpus, *args, **kwargs)

        self.subtractions = subtractions
        self.replacements = replacements

        # let's make words less weird
        self.words, self._words = _unstack_words(self.words)
        self._word_edges = [] # type: typing.List[typing.Tuple[str, str, str], ...]


    @property
    def word_edges(self) -> typing.List[typing.Tuple[str, str, str]]:
        """
        word_trees except for just a list of the edges
        after they have been made unique by calling set()

        Returns:
            [(from_word, transformation, to_word),...]
        """
        if len(self._word_edges) == 0:
            _word_edges = []
            for tree in self.word_trees.values():
                _word_edges.extend(tree)
            self._word_edges = list(set(_word_edges))
        return self._word_edges


    def recurse_word(self, word:str, min_test_word:int=2, min_clipped_word:int=3) -> typing.Dict[str, typing.Tuple[typing.Tuple[str,str,str]]]:
        """
        Recurse a single word -- see :meth:`.recurse_all_words` for args

        .. note::

            this could be made about a zillion times faster by vectorizing with pandas...
        """


        # idk lazy way to unpack args when passed in parallel
        if isinstance(word, tuple) and len(word) == 3:
            word, min_test_word, min_clipped_word = word

        # test all sub-words, iterating by length of subword
        # don't test words that would make a clipped word shorter than
        # min_clipped_word
        edges = []
        for test_word in self.words:
            if len(test_word)<min_test_word or len(test_word)>=len(word):
                continue

            if self.internal_only and \
                    (word.startswith(test_word) or word.endswith(test_word)):
                continue

            if test_word in word:
                if self.subtractions:
                    clipped_word = word.replace(test_word,'')
                    if len(clipped_word) > min_clipped_word and clipped_word in self._words.keys():
                        edges.append((word, test_word, clipped_word))

                if self.replacements:
                    for replacement_word in self.words:
                        if len(test_word)<min_test_word:
                            continue
                        replaced_word = word.replace(test_word, replacement_word)
                        if replaced_word in self._words.keys():
                            edges.append((word, '_'.join((test_word, replacement_word)), replaced_word))


        return {word:tuple(edges)}


    def recurse_all_words(self,
                          min_include_word:int=9,
                          min_test_word:int=2,
                          min_clipped_word:int=3,
                          max_depth:int=0,
                          n_procs:int=12,
                          batch_size:int=100):
        """
        Populate :attr:`.word_trees` by searching recursively through words for recurse words

        Args:
            min_include_word (int): Minimum length of original words to test
            min_test_word (int): Minimum size of subwords to test splicing subwords with
            min_clipped_word (int): Minimum size of the resulting
                spliced/clipped word to be considered for additional recursive subwords
            max_depth (int): Maximum recursion depth to allow, if 0, infinite
            n_procs (int): Number of processors to spawn in the multiprocessing pool
        """
        test_words = [word for word in self.words if
                      word not in self.word_trees.keys() and len(word) > min_include_word]

        iterator = zip(
            test_words,
            repeat(min_test_word),
            repeat(min_clipped_word)
        )

        hit_pbar = tqdm(position=0,leave=True)
        progress_pbar = tqdm(position=1, total=len(test_words), leave=True)

        with mp.Pool(n_procs) as pool:

            for word_tree in pool.imap_unordered(self.recurse_word, iterator, chunksize=batch_size):

                if len(word_tree)>0:
                    # get the root word by just digging into the word tree
                    # until we get the first string
                    # then use that to index for laziness sake
                    self.word_trees.update(word_tree)

                    # count ya money
                    hit_pbar.update()
                # count ya time
                progress_pbar.update()

    def make_graph(self, root_word: typing.Optional[str] = None, graph_attr: dict = {},
                   depth:int=0,
                   node_attr: dict = {},
                   edge_attr: dict = {},
                   translate=True) -> pgv.AGraph:

        edges = self.word_edges


        if root_word is not None:
            if len(self.corpus._retranslate_tul) > 0:
                root_word = self.corpus._retranslate_tul[root_word.lower()]
            edges = [edge for edge in edges if edge[0] == root_word]
            if depth >0:
                for depth_n in range(depth):
                    to_edges = [edge[2] for edge in edges]
                    for to_edge in to_edges:
                        try:
                            edges.extend(self.word_trees[to_edge])
                        except KeyError:
                            pass
                    edges = list(set(edges))

        if len(self.corpus._retranslate_lut) > 0:
            edges = [tuple(self.corpus._retranslate_lut[word] for word in edge) for edge in edges]

        print('adding edges to graph...')
        g = pgv.AGraph(directed=True)
        for edge in tqdm(edges):
            g.add_edge(edge[0], edge[2], label=edge[1])

        if len(edges)>5000:
            splines = False
        else:
            splines = True

        g.graph_attr.update({
            'fontname': "Helvetica",
            'rankdir': 'LR',
            'nodesep': 1,
            'ranksep': 1,
            'overlap': 'scale',
            'splines': splines
        })

        g.node_attr.update({
            'shape': 'rectangle',
            'penwidth': 2,
            'fontname': 'Helvetica',
            'style': 'rounded'
        })

        g.edge_attr.update({
            'color': '#666666',
            'arrowsize': 0.5,
            'arrowhead': 'open',
            'labelfontcolor': '#666666'
        })

        g.graph_attr.update(graph_attr)
        g.node_attr.update(node_attr)
        g.edge_attr.update(edge_attr)

        return g


def _unstack_words(words: typing.Dict[int, list]) -> typing.Tuple[typing.Tuple[str], typing.Dict[str,int]]:
    """
    take the words of Recurser to those of Graph_Recurser

    Args:
        words ():

    Returns:
        replacements for words and _words
    """
    words_out = [] # type: typing.List[str]
    _words_out = {} # type: typing.Dict[str, int]
    for word_list in words.values():
        words_out.extend(word_list)
        _words_out.update({word:1 for word in word_list})

    return tuple(sorted(set(words_out))), _words_out
