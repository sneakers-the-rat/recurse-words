from pathlib import Path
from recurse_words import Recurser

word_file = Path.home() / 'git/english-words/words_alpha.txt'
save_file = Path.home() / 'Dropbox/stupid_bullshit_projects/word_trees_2.pck'

recurser = Recurser(word_file)
if save_file.exists():
    recurser.load(save_file)

# --------------------------------------------------
# recurse the words!!
# see help(recurser.recurse_all_words) for arg details
# --------------------------------------------------
try:
    recurser.recurse_all_words(
        min_include_word=6,
        min_test_word=2,
        min_clipped_word=3,
        max_depth=100)
finally:
    recurser.save(save_file)

# --------------------------------------------------
# draw some graphs!
# --------------------------------------------------
output_dir = Path().cwd()

# draw the words with the most leaves, most dense, and greatest depth
words_2_draw = list(recurser.by_leaves[max(recurser.by_leaves.keys())].keys())
words_2_draw.extend(list(recurser.by_density[max(recurser.by_density.keys())].keys()))
words_2_draw.extend(list(recurser.by_depth[max(recurser.by_depth.keys())].keys()))

# plus some other ones i think are neat
words_2_draw.extend(['collaborationists', 'shallowpated', 'bespattering'])
# ['denominative',
#  'denominates',
#  'presuppositionless',
#  'collaborationists',
#  'shallowpated',
#  'bespattering']

recurser.draw_graph(words_2_draw, output_dir, '.png')
