# BGCLens Validation Samples

Sample sets for the two validation use cases (see `validation-bgclens-usecases.md`).
Each set is 6 genomes (within the 5–7 target). All accessions below were verified against
NCBI / BacDive / primary literature at build time.

## Heads-up (why this is CSVs, not FASTA)
This package intentionally does **not** ship the genome sequences. BGCFlow ingests genomes
by NCBI accession and downloads them itself — so the deliverable is a ready-to-run
`samples.csv` for each use case. antiSMASH-DB is the *browse/pick* surface; the assemblies
you actually feed BGCFlow come from NCBI. One BGCFlow run fetches everything.

---

## UC-A — Multi-organism panel (breadth)
`uc_a_multi_organism_samples.csv` — 6 different species across 3 phyla, all BGC-rich, so the
cross-taxa / GCF-grouping / diversity checks have real signal.

| Accession | Organism | Phylum | Notable BGC(s) |
|-----------|----------|--------|----------------|
| GCF_000203835.1 | *Streptomyces coelicolor* A3(2) | Actinomycetota | actinorhodin, undecylprodigiosin, CDA (model, ~20+ BGCs) |
| GCF_000009765.2 | *Streptomyces avermitilis* MA-4680 | Actinomycetota | avermectin (~30 BGCs) |
| GCF_000171635.1 | *Saccharopolyspora erythraea* NRRL 2338 | Actinomycetota | erythromycin |
| GCF_000196835.1 | *Amycolatopsis mediterranei* U32 | Actinomycetota | rifamycin |
| GCF_000009045.1 | *Bacillus subtilis* subsp. *subtilis* 168 | Bacillota | surfactin, bacillaene, subtilosin (~14 regions) |
| GCF_000012685.1 | *Myxococcus xanthus* DK 1622 | Myxococcota | myxovirescin, myxalamid, myxochelin |

Rationale: four different actinomycete genera (where most BGCs live) plus a firmicute and a
myxobacterium give genuine taxonomic spread while keeping every genome BGC-dense — the panel
stresses cross-taxa handling without wasting slots on BGC-poor genomes.

## UC-B — Single organism, multiple assemblies (consistency)
`uc_b_single_organism_multi_assembly_samples.csv` — 6 strains of **one species**,
*Bacillus velezensis* (>98% ANI across strains). Near-redundant inputs are exactly what
stresses the consistency / "same BGC called across assemblies" / dereplication checks.

| Accession | Strain |
|-----------|--------|
| GCF_000015785.2 | FZB42 (model plant-growth-promoting strain) |
| GCF_000685725.1 | SQR9 |
| GCF_002117165.1 | CBMB205 |
| GCF_000769555.1 | JS25R |
| GCF_001266815.1 | OB9 |
| GCF_001266825.1 | B26 |

Rationale: *B. velezensis* carries a conserved, well-characterized BGC set (surfactin,
bacillaene, fengycin, difficidin, macrolactin, bacillibactin). High similarity between strains
means the *expectation* is high concordance — so any inconsistency in cluster calls,
or spurious "novelty," is a real finding rather than biological noise.

---

## How to run (BGCFlow)
1. Create a project dir per use case, e.g. `config/uc_a/` and `config/uc_b/`.
2. Drop the matching CSV in as `samples.csv` (rename accordingly).
3. Register each project in your BGCFlow `config.yaml` `projects:` list.
4. Run BGCFlow — it downloads the assemblies from NCBI by accession and executes
   Prokka / antiSMASH / GTDB-Tk, producing the outputs BGCLens ingests.

> Column schema here is `genome_id, source, organism, genus, species, strain,
> closest_placement_reference`. Confirm it matches your installed BGCFlow version; older/newer
> versions occasionally tweak optional columns. `source=ncbi` triggers the download.

## Browse before you run (optional)
antiSMASH-DB precomputed results, where available, follow:
`https://antismash-db.secondarymetabolites.org/output/<ACCESSION>/index.html`
(e.g. `.../output/GCF_000009045.1/index.html` for *B. subtilis* 168). Not every accession is
in antiSMASH-DB; BGCFlow computes fresh antiSMASH results regardless.

## Verification note
Accessions confirmed via NCBI Datasets, BacDive, and primary genome-announcement papers.
The only version-sensitive one to double-check is *S. avermitilis* — GCF_000009765.2 is the
classic MA-4680 reference (an alternate NBRC re-sequence, GCF_000764715.1, also exists).
