import multiprocessing as mp
from itertools import repeat
import pickle
from pathlib import Path
import typing

from tqdm import tqdm
import pygraphviz as pgv

from recurse_words.corpi import get_corpus



class Recurser(object):
    """
    Find words that have words inside them that when you delete the inside word the
    letters that are left are still a word

    Attributes:
        words (typing.Dict[int, typing.List[str,...]]):
            Dict of Lists of words ordered by word length,
            eg. length-4 words are words[4]
        _words: :attr:`Recurser.words` only instead of a list, a dict of dicts
            with words as keys and all values == 1 for faster lookups
        word_trees: dict of list of tuples, each tuple consists of
            ``('original_word', 'subword', 'sliced_word')``,
            since each original word can have multiple subword,
            they're combined in nested lists
    """

    def __init__(self, corpus:str, internal_only=True):
        """
        Args:
            corpus (path): text corpus! if a file, use the default corpi.Txt corpus loader,
                otherwise use the `'name'` attribute of the loader like "english"
            internal_only (bool): Whether to consider matching strings only if they are
                in the interior of the word, as opposed to the beginning or end (ie. exclude
                matches that are prefixes/suffixes).
        """
        corpus_obj = get_corpus(corpus)
        if corpus_obj is None:
            self.corpus = get_corpus('txt')(path=corpus)
        else:
            self.corpus = corpus_obj()

        self.internal_only = internal_only
        self.words = {} # type: typing.Dict[int, typing.List[str,...]]
        self._words = {}
        # self.words but instead of a list of words, a dict with keys
        # of all the words mapped to 1 for faster lookups

        self._word_chains = []
        self._by_density = {}
        self._by_absolute_density = {}
        self._by_depth = {}
        self._by_leaves = {}

        self.load_words(self.corpus.corpus)
        self.word_trees = {} # type: typing.Dict[str, typing.List[typing.Union[typing.List, typing.Tuple[str,str,str]],...]]

    def load_words(self, corpus:typing.List[str]):
        word_lengths = {}
        # make another one where instead of a list of words we store a
        # dict of words mapped to 1 for faster lookup
        word_lengths_dict = {}
        for word in tqdm(corpus):
            word = word.rstrip('\r\n')
            if len(word) in word_lengths.keys():
                word_lengths[len(word)].append(word)
                word_lengths_dict[len(word)][word] = 1
            else:
                word_lengths[len(word)] = [word]
                word_lengths_dict[len(word)] = {word:1}

        self.words = word_lengths
        self._words = word_lengths_dict

    def recurse_word(self, word:str, min_test_word:int=2, min_clipped_word:int=3, max_depth:int=0, current_depth:int=0):
        """
        Recurse a single word -- see :meth:`.recurse_all_words` for args
        """
        if current_depth > 0:
            # dict lookups are supr cheap and each word should
            # only ever be added once so might as well not do it again...
            if word in self.word_trees.keys():
                return self.word_trees[word]

        # idk lazy way to unpack args when passed in parallel
        if isinstance(word, tuple) and len(word) == 4:
            word, min_test_word, min_clipped_word, max_depth = word

        # test all sub-words, iterating by length of subword
        # don't test words that would make a clipped word shorter than
        # min_clipped_word
        word_length = len(word)
        word_pairs = []
        for length in range(min_test_word,
                            max(word_length-min_clipped_word+1,
                                min_test_word+1)):
            if length not in self.words.keys():
                continue
            for test_word in self.words[length]:
                clip_chain = []
                if test_word in word:
                    # take the inner word out of the outer word and see what happens
                    clipped_word = word.replace(test_word, '')

                    if len(clipped_word)<min_clipped_word:
                        continue

                    # aka if we want to exclude suffixes and prefixes...
                    if self.internal_only:
                        if word.startswith(test_word) or word.endswith(test_word):
                            continue

                    # dict lookup here is faster
                    # the --reel deel test-- if the clipped word is a real word
                    if len(clipped_word) in self._words.keys() and \
                            clipped_word in self._words[len(clipped_word)].keys():

                        clip_chain.append((word, test_word, clipped_word))

                        # a lil recursion magic here to fill in the rest of the tree...
                        if current_depth < max_depth or max_depth == 0:
                            recurse_tups = self.recurse_word(
                                clipped_word, min_test_word,
                                min_clipped_word, max_depth,
                                current_depth+1
                            )
                            clip_chain.extend(recurse_tups)

                if len(clip_chain)>0:
                    word_pairs.append(clip_chain)

        return word_pairs

    def recurse_all_words(self,
                          min_include_word:int=9,
                          min_test_word:int=2,
                          min_clipped_word:int=3,
                          max_depth:int=0,
                          n_procs:int=12):
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
        hit_pbar = tqdm(position=2)
        with mp.Pool(n_procs) as pool:
            for length in tqdm(range(min_include_word, max(self.words.keys())), position=0):
                # skip discontinuities in word lengths (???)
                if length not in self.words.keys():
                    continue

                # filter words if they are already in the word_tree :)
                test_words = [word for word in self.words[length] if word not in self.word_trees.keys()]
                if len(test_words)==0:
                    continue

                # iterate over the test words,
                # repeat the other params just for the weird parallelization syntax
                iterator = zip(
                    test_words,
                    repeat(min_test_word),
                    repeat(min_clipped_word),
                    repeat(max_depth)
                )

                # --------------------------------------------------
                # doin the it
                # --------------------------------------------------
                word_pbar = tqdm(total=len(test_words), position=1)
                for word_tree in pool.imap_unordered(self.recurse_word, iterator, chunksize=100):

                    if len(word_tree)>0:
                        # get the root word by just digging into the word tree
                        # until we get the first string
                        inner_tree = word_tree.copy()
                        while isinstance(inner_tree, (tuple, list)):
                            inner_tree = inner_tree[0]

                        # then use that to index for laziness sake
                        self.word_trees[inner_tree] = word_tree

                        # count ya money
                        hit_pbar.update()
                    # count ya time
                    word_pbar.update()


    def save(self, filename:Path):
        with open(filename, 'wb') as out_file:
            pickle.dump(self.word_trees, out_file)
        print(f"Saved word trees to {filename}")

    def load(self, filename:Path):
        with open(filename, 'rb') as in_file:
            self.word_trees = pickle.load(in_file)

    @property
    def word_chains(self) -> typing.List[typing.List[str]]:
        """
        chains of trees, without tuple structure.

        Returns:

        """
        raise NotImplementedError("gettouttahere ya punk kids")

    def _reindex_trees(self, func) -> dict:
        """
        Despite how the internal variables might describe it,
        reindex the word trees according to some function
        that takes the tree itself and returns some index, like an
        integer... or whatever...

        Args:
            func (callable): give it a tree, return something else?

        Returns:
            dict
        """
        _private_attr = {}
        for word, trees in sorted(self.word_trees.items()):
            tree_len = func(trees)
            if tree_len not in _private_attr.keys():
                _private_attr[tree_len] = {word:trees}
            else:
                _private_attr[tree_len][word] = trees
        return _private_attr

    @property
    def by_leaves(self):
        """
        :attr:`.word_trees` reindexed by total number of unique leaves
        """
        if len(self._by_leaves) == 0:
            self._by_leaves = self._reindex_trees(count_leaves)
        return self._by_leaves

    @property
    def by_density(self):
        """
        :attr:`.word_trees` reindexed by :func:`.dedupe_density`

        aka the total unique number of edges
        """
        if len(self._by_density) == 0:
            self._by_density = self._reindex_trees(dedupe_density)
        return self._by_density

    @property
    def by_absolute_density(self):
        """
        :attr:`.word_trees` reindexed by :func:`.recursive_density`

        aka by counting the total number of nodes *and edges* in the tree,
        allowing for repeated paths
        """
        if len(self._by_absolute_density) == 0:
            self._by_absolute_density = self._reindex_trees(recursive_density)
        return self._by_absolute_density

    @property
    def by_depth(self):
        """
        :attr:`.word_trees` reindexed by :func:`.recursive_depth`

        aka by counting the maximum depth of the tree
        """
        if len(self._by_depth) == 0:
            self._by_depth = self._reindex_trees(recursive_depth)
        return self._by_depth

    def draw_graph(self, trees:typing.Union[dict, list, str], output_dir:Path, extension:str=".svg",
                   graph_attr:dict={}, node_attr:dict={},edge_attr:dict={},translate=True):
        """
        Draw a network diagram of a recurseword tree

        Args:
            trees (dict, list, str): either a dictionary of {word: tree}, a list of [words], or a single word
            output_dir (Path): output directory, file will be named ``word{extension}``
            extension (str): default ``'.svg'`` , but any output that pygraphciz supports
            graph_attr (dict): supplementary parameters for graph attributes
            node_attr (dict): ... node attributes...
            edge_attr (dict): ... edge
        """
        output_dir = Path(output_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True)

        if isinstance(trees, str):
            trees = {trees:self.word_trees[trees]}
        elif isinstance(trees, list):
            trees = {word:self.word_trees[word] for word in trees}

        for word, tree in tqdm(trees.items()):
            if hasattr(self.corpus, '_phone_to_word') and translate is True:
                word = self.corpus._phone_to_word[word]
                tree = recursive_translate(tree, self.corpus._phone_to_word)
            g = pgv.AGraph(directed=True,
                           strict=False,
                           title=word)
            g.graph_attr.update({
                'fontname': "Helvetica",
                'rankdir': 'LR',
                'nodesep': 0.6,
                'ranksep': 1
            })

            g.node_attr.update({
                'shape': 'rectangle',
                'penwidth':2,
                'fontname':'Helvetica',
                'style':'rounded'
            })

            g.edge_attr.update({
                'color': '#666666',
                'arrowsize':0.5,
                'arrowhead':'open',
                'labelfontcolor':'#666666'
            })

            g.graph_attr.update(graph_attr)
            g.node_attr.update(node_attr)
            g.edge_attr.update(edge_attr)

            for node_from, label, node_to in set(recursive_walk(tree)):
                g.add_edge(node_from, node_to, label=label)

            g.layout('dot')
            g.draw(str((output_dir / word).with_suffix(extension)))




def recursive_walk(in_list):
    for item in in_list:
        if isinstance(item, list):
            yield from recursive_walk(item)
        else:
            yield item

def recursive_density(in_list) -> int:
    count = 0
    for item in in_list:
        if isinstance(item, list):
            count += recursive_density(item)
        else:
            count += 1
    return count

def dedupe_density(in_list) -> int:
    """
    recursive density doesn't dedupe...
    so the same path can appear multiple times.

    instead we can just recursive walk and take the length of the set of all the unique tuples
    """
    return len(set(recursive_walk(in_list)))



def recursive_depth(in_list) -> int:
    depths = []
    for item in in_list:
        if isinstance(item, list):
            depths.append(recursive_depth(item))
    if len(depths) > 0:
        return 1 + max(depths)
    return 1

def count_leaves(in_list) -> int:
    words = []
    # gather all unique words
    for parent, replace, child in recursive_walk(in_list):
        words.extend([parent, child])
    return len(set(words))


def recursive_translate(in_list:list, lut:dict) -> list:
    translated = []
    for item in in_list:
        if isinstance(item, list):
            translated.append(recursive_translate(item, lut))
        else:
            translated.append(tuple((lut[i] for i in item)))
    return translated



