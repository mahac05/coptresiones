import timeit
import itertools

class DummyWidget:
    def apply_theme(self, t, is_dark):
        pass

# Setup some dummy data
conv_file_widgets = {i: DummyWidget() for i in range(1000)}
comp_file_widgets = {i: DummyWidget() for i in range(1000)}
lect_file_widgets = {i: DummyWidget() for i in range(1000)}

def using_lists():
    for fw in list(conv_file_widgets.values()) + list(comp_file_widgets.values()) + list(lect_file_widgets.values()):
        fw.apply_theme(None, False)

def using_chain():
    for fw in itertools.chain(conv_file_widgets.values(), comp_file_widgets.values(), lect_file_widgets.values()):
        fw.apply_theme(None, False)

# Warmup
using_lists()
using_chain()

lists_time = timeit.timeit(using_lists, number=1000)
chain_time = timeit.timeit(using_chain, number=1000)

print(f"Using lists: {lists_time:.4f} seconds")
print(f"Using chain: {chain_time:.4f} seconds")
if lists_time > 0:
    print(f"Improvement: {(lists_time - chain_time) / lists_time * 100:.2f}%")
