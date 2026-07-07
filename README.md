# Bioprospecting Candidate Finder

An AI-assisted workflow tool to discover and prioritize microbial, enzyme, and metabolite candidates from literature and genome-mining outputs.
I want to build an AI-assisted workflow layer for prioritizing microbial, enzyme, and metabolite candidates from literature and genome-mining results. The tool would take a broad research goal, such as identifying microbes with antimicrobial potential or lignocellulose-degrading enzymes, and turn it into a reproducible candidate-discovery workflow: extracting organisms and experimental evidence from papers, collecting genome/accession metadata, parsing antiSMASH outputs for biosynthetic gene clusters, interpreting BGC similarity against known references such as MIBiG, checking functional enzyme annotations for traits such as carbohydrate degradation, and ranking candidates by evidence strength, novelty, biological relevance, and validation feasibility. To make the demo technically concrete, I would use termite gut microbes as a proof-of-concept system, since their symbiotic microbiomes are strongly associated with biomass degradation and may also encode useful secondary metabolite pathways. The final output would be a structured report with ranked candidates, predicted enzyme or BGC/metabolite class, source environment, supporting evidence, confidence and novelty scores, suggested experimental assay, and next validation step. The goal is to help researchers move from a broad bioprospecting question to a reviewable, validation-ready shortlist using Claude together with established bioinformatics tools rather than relying on an unstructured literature search alone.

## who am i

I am an AI engineer and part-time member of the Bioprospecting and Engineering of Advanced Microbial Solutions Lab, where I mainly explore how LLMs and AI agents can support bioinformatics workflows.  My day-to-day work focuses on designing AI-assisted research workflows, building evaluation benchmarks for bioinformatics use cases, and testing how LLMs can help with tasks such as literature review, workflow orchestration, data interpretation, reproducibility checks, and scientific reasoning.  I work at the intersection of AI engineering and computational biology: translating biological research problems into structured AI workflows, evaluating whether the outputs are reliable, and improving the process so researchers can move from raw data and scattered context into clearer, reproducible analysis.

## Use Case

The proof-of-concept focuses on termite gut microbes as a source of lignocellulose-degrading enzymes and potentially bioactive secondary metabolites.

## Core Workflow

1. Extract candidate organisms from literature
2. Collect genome or accession metadata
3. Parse antiSMASH outputs for biosynthetic gene clusters
4. Parse CAZyme-style annotations for enzyme candidates
5. Score candidates by evidence, novelty, and validation feasibility
6. Generate a ranked candidate report

## Output

- Organism
- Predicted enzyme or compound/BGC
- Environmental source
- Evidence strength
- Novelty signal
- Experimental method
- Next validation step
