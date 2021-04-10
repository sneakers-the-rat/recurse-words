# recurse-words
find words that have other words in them that when you remove the inner word what's left is still a word

![An example word tree of such a kind](examples/img/collaborationists.png)

# installation

From pypi:

```
pip install recurse-words
```

From github:

```
git clone https://github.com/sneakers-the-rat/recurse-words
pip install ./recurse-words
# or
poetry install ./recurse-words
```

# usage

Point the recurser at a file that has a list of words,
for example [this one](https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt), 
and let 'er rip

```python
from recurse_words import Recurser

recurser = Recurser('path/to/some/words.txt')
recurser.recurse_all_words()
recurser.save('word_trees.pck')

# see word trees by a few metrics
# max tree depth
recurser.by_depth
# total number of leaves
recurser.by_leaves
# total number of edges
recurser.by_density
```

Draw network graphs!

```python
recurser.draw_graph('some_word', '/output/directory')
```

Auto-download different corpuses!

```python
recurser = Recurser(corpus='english')
recurser = Recurser(corpus='phonetic')
```

