#!/bin/bash

set -e

mkdir -p paired_somaticseq

somaticseq_parallel.py \
--somaticseq-train \
--algorithm        ada \
--output-directory paired_somaticseq \
--genome-reference tiny.fa \
--dbsnp-vcf        tiny_dbsnp.vcf \
--truth-snv        Varsim.somatic.truth.vcf \
--truth-indel      Varsim.somatic.truth.vcf \
--threads          3 \
paired \
--tumor-bam-file   tumor.markdup.bam \
--normal-bam-file  normal.markdup.bam \
--mutect2-vcf      paired_example/MuTect2.vcf \
--vardict-vcf      paired_example/VarDict.vcf \
--strelka-snv      paired_example/Strelka/results/variants/somatic.snvs.vcf.gz \
--strelka-indel    paired_example/Strelka/results/variants/somatic.indels.vcf.gz
