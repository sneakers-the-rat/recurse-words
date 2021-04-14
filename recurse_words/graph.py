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

fnt = ImageFont.truetype('/Users/jonny/Library/Fonts/FreeSans-LrmZ.ttf')

from recurse_words import Graph_Recurser

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
