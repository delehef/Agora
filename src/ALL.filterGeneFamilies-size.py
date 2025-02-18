#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# AGORA v3.1
# python 3.5
# Copyright © 2006-2022 IBENS/Dyogen, 2020-2021 EMBL-European Bioinformatics Institute, 2021-2022 Genome Research Ltd : Matthieu MUFFATO, Alexandra LOUIS, Thi Thuy Nga NGUYEN, Hugues ROEST CROLLIUS
# mail : agora@bio.ens.psl.eu
# This is free software; you may copy, modify and/or distribute this work under the terms of the GNU General Public License, version 3 or later and the CeCiLL v2 license in France

__doc__ = """
    Filter ancestral genes according to the number of extant genes

    Usage:
        src/ALL.filterGeneFamilies-size.py example/data/Species.nwk A0 \
                -IN.ancGenesFiles=example/results/ancGenes/all/ancGenes.%s.list.bz2 \
                -IN.genesFiles=example/data/genes/genes.%s.list.bz2 \
                -OUT.ancGenesFiles=example/results/ancGenes/size-%s/ancGenes.%s.list.bz2 \
                1.0,0.9,0.77 1.0,1.1,1.33
"""

import os.path
import sys

import utils.myGenomes
import utils.myPhylTree
import utils.myTools
from utils.myTools import file

arguments = utils.myTools.checkArgs(
    [("speciesTree", file), ("target", str), ("minSize", str),("maxSize", str)],
    [("IN.genesFiles", str, ""), ("IN.ancGenesFiles", str, ""), ("OUT.ancGenesFiles", str, "")],
    __doc__)

phylTree = utils.myPhylTree.PhylogeneticTree(arguments["speciesTree"])
target = phylTree.officialName[arguments["target"]]

lstAncGenes = {}
dicAncGenes = {}
for anc in sorted(phylTree.listAncestr.union(phylTree.listSpecies)):
    if phylTree.dicParents[anc][target] == target:
        ancPath = arguments["IN.ancGenesFiles"] % phylTree.fileName[anc]
        if os.path.exists(ancPath):
            ancGenes = utils.myGenomes.Genome(arguments["IN.ancGenesFiles"] % phylTree.fileName[anc])
            lstAncGenes[anc] = [gene.names for gene in ancGenes.lstGenes[None]]
            del ancGenes
        elif anc in phylTree.listSpecies:
            # Use the genesFiles if ancGenesFiles don't cover extant species
            genome = utils.myGenomes.Genome(arguments["IN.genesFiles"] % phylTree.fileName[anc])
            # Only the first "name" of each gene matters, it's the one that is expected to be used
            # in the gene trees or orthology groups. Need to add None to match the way ancestral
            # genes are usually recorded
            lstAncGenes[anc] = [[None, gene.names[0]] for gene in genome]
            del genome
        dicGenes = {}
        for (i, names) in enumerate(lstAncGenes[anc]):
            for s in names:
                dicGenes[s] = i
        dicAncGenes[anc] = dicGenes

minsizes = [float(x) for x in arguments["minSize"].split(",")]
maxsizes = [float(x) for x in arguments["maxSize"].split(",")]

# Initialisation
print("Structure creation ...", end=' ', file=sys.stderr)
desc = {}
notseen = {}
deleted = {}
for anc in lstAncGenes:
    n = len(lstAncGenes[anc])
    notseen[anc] = set(range(n))
    desc[anc] = [[] for _ in range(n)]
    deleted[anc] = set()
todo = []
print("OK", file=sys.stderr)

def mkStruct(anc):
    if anc in sorted(phylTree.items):
        print("Processing ancGenome", anc, file=sys.stderr)
        # New ancestral genes have to be analyzed
        for i in notseen[anc]:
            todo.append((anc, i))
        for (newanc, _) in phylTree.items[anc]:
            dicGenes = dicAncGenes[newanc]
            for (i, names) in enumerate(lstAncGenes[anc]):
                s = set((dicGenes[s] for s in names[1:] if s in dicGenes))
                #print >>sys.stderr, i, names, s
                # links father/children
                for x in s:
                    #print >>sys.stderr, x
                    notseen[newanc].remove(x)
                    desc[anc][i].append((newanc, x))
                # Duplicates have to be analyzed
                if (len(s) > 1) and (newanc in phylTree.listAncestr):
                    todo.extend((newanc, x) for x in s)
            mkStruct(newanc)
mkStruct(target)
#print >> sys.stderr, len(todo), "todo", todo[0], todo[-1]

# Combine calc results on each extant species gene.

def treeWrapper(calc):
    def f(anc, i):
        if anc in phylTree.listSpecies:
            return calc(anc, i)
        if i in deleted[anc]:
            return []
        l = []
        for x in desc[anc][i]:
            l.extend(f(*x))
        return l
    return f


# non 2-X species name list
@treeWrapper
def getSpeciesList(anc, i):
    return [] if anc in phylTree.lstEsp2X else [anc]

# name genes list
@treeWrapper
def getGeneNames(anc, i):
    return lstAncGenes[anc][i][1:]

import copy

for size in range(len(minsizes)):
    todo_cp = copy.copy(todo)
    # Browsing all nodes to study
    while len(todo_cp) > 0:
        (anc, i) = todo_cp.pop()
        if anc not in phylTree.listAncestr:
            continue
        sr = getSpeciesList(anc, i)
        st = set(phylTree.species[anc]).difference(phylTree.lstEsp2X)

        if (len(set(sr)) >= minsizes[size] * len(st)) and (len(sr) <= maxsizes[size] * len(set(sr))):
            pass
        else:
            # the node is deleted, as the son if only one.
            deleted[anc].add(i)
            while len(desc[anc][i]) == 1:
                (anc, i) = desc[anc][i][0]
                if anc not in phylTree.listAncestr:
                    break
                deleted[anc].add(i)
            else:
                todo_cp.extend(desc[anc][i])


    # Writing files
    for anc in sorted(lstAncGenes):
        if anc not in phylTree.listAncestr:
            continue
        print("Writing families of %s (size %s-%s)..." % (anc, minsizes[size], maxsizes[size]), end=' ', file=sys.stderr)
        n = 0
        outFile = arguments["OUT.ancGenesFiles"] % ("%s-%s" % (minsizes[size], maxsizes[size]), phylTree.fileName[anc])
        f = utils.myFile.openFile(outFile, "w")
        for (i, names) in enumerate(lstAncGenes[anc]):
            s = getGeneNames(anc, i)
            if len(s) > 0:
                # Conserved family (maybe with less descendants)
                n += 1
                s = set(s)
                s.add(names[0])
                print(" ".join(x for x in names if x in s), file=f)
            else:
                # Empty family , this is necessary to conserved indexation (compared to all families)
                print(names[0], file=f)
        f.close()
        deleted[anc] = set()
        print(len(desc[anc]), "->", n, "OK", file=sys.stderr)

