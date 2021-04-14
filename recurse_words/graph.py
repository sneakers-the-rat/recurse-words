import typing
import warnings

import datashader as ds
import numpy as np
from datashader.layout import forceatlas2_layout
from datashader.bundling import hammer_bundle
import pandas as pd
import datashader.transfer_functions as tf
from colorcet import fire

from PIL import ImageDraw, ImageFont

from recurse_words import Graph_Recurser, Recurser

class Graph(object):
    """
    Represent and manipulate a :class:`.Recurser` object as a graph!

    Attributes:
        filtered_edges (:class:`pandas.DataFrame`): Edges after some call to :meth:`.Graph.filter`, initialized
            as :attr:`.Graph.edges`.
    """

    def __init__(self, recurser:Graph_Recurser):
        self._edges = pd.DataFrame()
        self._untranslated_edges = pd.DataFrame()
        self._filtered_edges = pd.DataFrame()

        self.recurser = recurser


    def _translate_edges(self, edges: pd.DataFrame) -> pd.DataFrame:
        for col in edges.columns:
            edges[col].replace(
                to_replace=self.recurser.corpus._retranslate_lut,
                inplace=True
            )
        return edges

    def _sort_edges(self, edges: pd.DataFrame) -> pd.DataFrame:
        """
        Sort edges in order of source, subword, replacement, target
        """
        return edges.sort_values(by=('source', 'subword', 'replacement', 'target'),
                                axis=1, ignore_index=True)

    @property
    def edges(self) -> pd.DataFrame:
        """
        Pandas dataframe of all edges, in columns:

        ``('source', 'subword', 'replacement', 'target')``

        If corpus has a translation layer, edges should be the translated version of the edges.

        Returns:
            :class:`pandas.DataFrame`
        """
        if len(self._edges) == 0:
            self._edges = self.untranslated_edges.copy()

            if len(self.recurser.corpus._retranslate_lut)>0:
                self._edges = self._sort_edges(self._translate_edges(self._edges))


        return self._edges

    @property
    def untranslated_edges(self) -> pd.DataFrame:
        """
        Precurser to :attr:`.Graph.edges`, gets edges before they're translated back to human-readable.

        Equivalent to edges if there is no translation layer

        Returns:
            :class:`pandas.DataFrame`
        """
        if len(self._untranslated_edges) == 0:
            _edges = pd.DataFrame(self.recurser.word_edges,
                                       columns=['source', 'label', 'target'])
            _edges[['subword', 'replacement']] = _edges['label'].str.split('_', expand=True)
            _edges.drop('label', axis=1, inplace=True)
            _edges = _edges[['source', 'subword', 'replacement', 'target']]
            self._untranslated_edges = self._sort_edges(_edges)
        return self._untranslated_edges


    @property
    def filtered_edges(self) -> pd.DataFrame:
        """
        Edges after being filtered by :meth:`.Graph.filter`

        Until then, equivalent to :attr:`.Graph.edges`

        Should be used by all graph generating mechanisms rather than
            :attr:`.Graph.edges`, which is intended to be the immutable source of edges.

        Returns:
            :class:`pandas.DataFrame`
        """
        if len(self._filtered_edges) == 0:
            self._filtered_edges = self.edges
        return self._filtered_edges


    def filter(self, root_word: str, depth:int=0) -> pd.DataFrame:
        """
        Filter the graph from some root word and depth

        Note that this words off the original, untranslated edges to avoid any loss of meaning
        that might happen in the mapping from the network edge space to the human-readable space,
        eg. in the :class:`.corpi.CMUDict` phonetic corpus, multiple english words map to a single
        phonetic representation, so when translated back to english one is chosen at random.
        Filtering in the network space avoids the ambiguity, hopefully.

        Args:
            root_word (str): Root word to
            depth (int): number of additional steps to take. 0 returns just the words immediately
                connected to the root word.

        Returns:
            :class:`pandas.DataFrame`
        """

        if len(self.recurser.corpus._retranslate_tul) > 0:
            root_word = self.recurser.corpus._retranslate_tul[root_word]

        filtered_edges = self.untranslated_edges[self.untranslated_edges['source'] == root_word]

        if depth > 0:
            _filtered = pd.DataFrame()
            for i in range(depth):
                _filtered = self.untranslated_edges[
                    self._untranslated_edges['source'].isin(
                        filtered_edges['target']
                    )
                ]

            filtered_edges = pd.concat((filtered_edges, _filtered))

        filtered_edges = self._sort_edges(filtered_edges)
        self._filtered_edges = filtered_edges.copy()
        return filtered_edges

    def make_datashader(self):
        # TODO
        pass













def datashader_network(recurser:Graph_Recurser,
                       root_word: typing.Optional[str] = None,
                        depth:int=0,
                       res=(10000,10000),
                       cmap_min=65):
    print('Extracting nodes and edges...')
    edges = recurser.word_edges.copy()

    if root_word is not None:
        if len(recurser.corpus._retranslate_tul) > 0:
            root_word = recurser.corpus._retranslate_tul[root_word.lower()]
        edges = [edge for edge in edges if edge[0] == root_word]
        if depth > 0:
            for depth_n in range(depth):
                to_edges = [edge[2] for edge in edges]
                for to_edge in to_edges:
                    try:
                        edges.extend(recurser.word_trees[to_edge])
                    except KeyError:
                        pass
                edges = list(set(edges))

    if len(recurser.corpus._retranslate_lut) > 0:
        edges = [tuple(recurser.corpus._retranslate_lut[word] for word in edge) for edge in edges]

    edges = list(set(edges))

    # filter self connections
    edges = [edge for edge in edges if edge[0] != edge[2]]

    # get unique words in edges (not just recurser.words which is all words)
    words = []
    for edge in edges:
        words.extend((edge[0], edge[2]))
    words = sorted(list(set(words)))

    #make their weirdo separated edge forms
    nodes = pd.DataFrame({'name': words})
    # get reverse df to get numbers from words
    nodes_rev = nodes.reset_index().set_index('name')

    df_edges = pd.DataFrame(edges, columns=('source', 'label', 'target'))
    edge_df = pd.DataFrame({'source':np.squeeze(nodes_rev.loc[df_edges.source].values),
                           'target':np.squeeze(nodes_rev.loc[df_edges.target].values)})

    print('Laying Out Network...')
    net_layout = forceatlas2_layout(nodes, edge_df)
    print('Bundling edges...')
    edge_layout = hammer_bundle(net_layout, edge_df)

    print('Constructing Canvas...')
    xr = net_layout.x.min(), net_layout.x.max()
    yr = net_layout.y.min(), net_layout.y.max()
    canvas = ds.Canvas(x_range=xr, y_range=yr, plot_width=res[0], plot_height=res[1])
    agg=canvas.points(net_layout, 'x', 'y')
    spread_points = tf.spread(tf.shade(agg, cmap=['#FFFFFF']), px=3, name='network!')
    spread_edges = tf.shade(canvas.line(edge_layout, 'x', 'y', agg=ds.count()), cmap=fire[cmap_min:], name='edges!')
    stack = tf.stack(spread_edges, spread_points, how='over', name='network!!!')
    stack = tf.set_background(stack, "#000000")
    return stack, net_layout, edge_layout


# img = tf.Image(stack).to_pil()
# img.save('/Users/jonny/Dropbox/stupid_bullshit_projects/recurse_words/test_shader_spider.png')

def draw_labels(stack, net_layout):
    pass
    # d = ImageDraw(tf.Image(stack).to_pil())
    #
    # for i, label in net_layout_norm.iterrows():
    #     d.text((label.x * img2.size[0], (1 - label.y) * img2.size[1]), label['name'], font=fnt, fill=(0, 0, 0))
    #
