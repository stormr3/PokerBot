# Source - https://stackoverflow.com/q/48429408
# Posted by Shinobii
# Retrieved 2026-11-05, License - CC BY-SA 3.0

import numpy
b = numpy.load('src\data\preflop_equity.npz')
print(b.files)
print(b['keys'])