#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# AGORA v3.1
# python 3.5
# Copyright © 2006-2022 IBENS/Dyogen, 2020-2021 EMBL-European Bioinformatics Institute, 2021-2022 Genome Research Ltd : Matthieu MUFFATO, Alexandra LOUIS, Thi Thuy Nga NGUYEN, Hugues ROEST CROLLIUS
# mail : agora@bio.ens.psl.eu
# This is free software; you may copy, modify and/or distribute this work under the terms of the GNU General Public License, version 3 or later and the CeCiLL v2 license in France

__doc__ = """
    Similar to a de-novo integration, but around existing blocks. This is typically run
    on singletons only, leaving the input blocks untouched.

    Usage:
        src/buildSynteny.integr-fusion.py example/data/Species.nwk A0 \
                example/results/pairwise/pairs-all/%s.list.bz2 \
                +onlySingletons \
                -IN.ancBlocks=example/results/ancBlocks/denovo-size-1.0-1.0.fillin-all/blocks.%s.list.bz2 \
                -OUT.ancBlocks=example/results/ancBlocks/denovo-size-1.0-1.0.fillin-all.fusion-all/blocks.%s.list.bz2 \
                -LOG.ancGraph=example/results/ancBlocks/denovo-size-1.0-1.0.fillin-all.fusion-all/graph.%s.txt.bz2
"""

import multiprocessing
import sys
import time

import utils.myFile
import utils.myGenomes
import utils.myGraph
import utils.myMaths
import utils.myPhylTree
import utils.myTools
from utils.myTools import file

# Arguments
arguments = utils.myTools.checkArgs(
    [("speciesTree", file), ("target", str), ("pairwise", str)],
    [("minimalWeight", int, 1), ("searchLoops", bool, True), ("onlySingletons", bool, False),
     ("nbThreads", int, 0),
     ("IN.ancBlocks", str, ""), ("OUT.ancBlocks", str, ""), ("LOG.ancGraph", str, "")],
    __doc__
)


def do(anc):
    # Redirect the standard output to a file
    ini_stdout = sys.stdout
    sys.stdout = utils.myFile.openFile(arguments["LOG.ancGraph"] % phylTree.fileName[anc], "w")

    graph = utils.myGraph.WeightedDiagGraph()
    (integr, singletons) = utils.myGraph.loadIntegr(arguments["IN.ancBlocks"] % phylTree.fileName[anc])
    if not arguments["onlySingletons"]:
        for (b, w) in integr:
            graph.addWeightedDiag(b, [x + 10000 for x in w])

    diags = utils.myGraph.loadConservedPairsAnc(arguments["pairwise"] % phylTree.fileName[anc])
    for x in diags:
        if not arguments["onlySingletons"] or ((x[0][0] in singletons) and (x[1][0] in singletons)):
            graph.addLink(*x)

    print("Blocs integres de %s ..." % anc, end=' ', file=sys.stderr)

    # cutting the graph
    graph.cleanGraphTopDown(arguments["minimalWeight"], searchLoops=arguments["searchLoops"])

    f = utils.myFile.openFile(arguments["OUT.ancBlocks"] % phylTree.fileName[anc], "w")
    s = []

    if arguments["onlySingletons"]:
        # If this option is set, the blocks are printed as they are
        for (b, w) in integr:
            print(utils.myFile.myTSV.printLine([anc, len(b),
                                                      utils.myFile.myTSV.printLine([x[0] for x in b], " "),
                                                      utils.myFile.myTSV.printLine([x[1] for x in b], " "),
                                                      utils.myFile.myTSV.printLine(w, " ")]), file=f)

    # Compute the blocks
    for (d, dw) in graph.getBestDiags():

        if len(d) == 1:
            continue

        da = [x[0] for x in d]
        ds = [x[1] for x in d]

        s.append(len(da))
        singletons.difference_update(da)
        print(utils.myFile.myTSV.printLine(
            [anc, len(da), utils.myFile.myTSV.printLine(da, " "), utils.myFile.myTSV.printLine(ds, " "),
             utils.myFile.myTSV.printLine(dw, " ")]), file=f)

    for x in singletons:
        print(utils.myFile.myTSV.printLine([anc, 1, x, 1, ""]), file=f)
    f.close()
    print(utils.myMaths.myStats.txtSummary(s), "+ %d singletons OK" % len(singletons), file=sys.stderr)

    # Revert to the true standard output
    sys.stdout.close()
    sys.stdout = ini_stdout


start = time.time()


# Load species tree and target ancestral genome
phylTree = utils.myPhylTree.PhylogeneticTree(arguments["speciesTree"])
targets = phylTree.getTargetsAnc(arguments["target"])

n_cpu = arguments["nbThreads"] or multiprocessing.cpu_count()
multiprocessing.Pool(n_cpu).map(do, sorted(targets))

print("Elapsed time:", (time.time() - start), file=sys.stderr)
