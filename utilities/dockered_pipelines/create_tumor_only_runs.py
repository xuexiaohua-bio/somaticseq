#!/usr/bin/env python3

import sys, argparse, os, re
from copy import copy
from datetime import datetime
from shutil import move

MY_DIR = os.path.dirname(os.path.realpath(__file__))
RepoROOT = os.path.join(MY_DIR, os.pardir, os.pardir)

sys.path.append( MY_DIR )
sys.path.append( os.path.join(MY_DIR, os.pardir) ) # utilities dir for Bed splitting
sys.path.append( RepoROOT + os.sep + 'somaticseq' )

import split_Bed_into_equal_regions as split_bed

with open(RepoROOT + os.sep + 'VERSION') as fn:
    line_i = fn.readline().rstrip()
    VERSION = line_i.split('=')[1].lstrip('v')

ts = re.sub(r'[:-]', '.', datetime.now().isoformat() )


def run():

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Variant Call Type, i.e., snp or indel
    parser.add_argument('-outdir',     '--output-directory',     type=str,   help='Absolute path for output directory', default=os.getcwd())
    parser.add_argument('-somaticDir', '--somaticseq-directory', type=str,   help='SomaticSeq directory output name',   default='SomaticSeq')
    parser.add_argument('-bam',        '--bam',                  type=str,   help='tumor bam file',       required=True)
    parser.add_argument('-name',       '--sample-name',          type=str,   help='tumor sample name',    default='TUMOR')
    parser.add_argument('-ref',        '--genome-reference',     type=str,   help='reference fasta file', required=True)
    parser.add_argument('-include',    '--inclusion-region',     type=str,   help='inclusion bed file',  )
    parser.add_argument('-exclude',    '--exclusion-region',     type=str,   help='exclusion bed file',  )
    parser.add_argument('-dbsnp',      '--dbsnp-vcf',            type=str,   help='dbSNP vcf file, also requires .idx, .gz, and .gz.tbi files', required=True)
    parser.add_argument('-cosmic',     '--cosmic-vcf',           type=str,   help='cosmic vcf file')
    parser.add_argument('-minVAF',     '--minimum-VAF',          type=float, help='minimum VAF to look for',)
    parser.add_argument('-action',     '--action',               type=str,   help='action for each mutation caller\' run script', default='echo')
    parser.add_argument('-somaticAct', '--somaticseq-action',    type=str,   help='action for each somaticseq.cmd',               default='echo')

    parser.add_argument('-mutect2',    '--run-mutect2',       action='store_true', help='Run MuTect2')
    parser.add_argument('-varscan2',   '--run-varscan2',      action='store_true', help='Run VarScan2')
    parser.add_argument('-vardict',    '--run-vardict',       action='store_true', help='Run VarDict')
    parser.add_argument('-lofreq',     '--run-lofreq',        action='store_true', help='Run LoFreq')
    parser.add_argument('-scalpel',    '--run-scalpel',       action='store_true', help='Run Scalpel')
    parser.add_argument('-strelka2',   '--run-strelka2',      action='store_true', help='Run Strelka2')
    parser.add_argument('-somaticseq', '--run-somaticseq',    action='store_true', help='Run SomaticSeq')
    parser.add_argument('-train',      '--train-somaticseq',  action='store_true', help='SomaticSeq training mode for classifiers')

    parser.add_argument('-snvClassifier',   '--snv-classifier',    type=str, help='action for each .cmd')
    parser.add_argument('-indelClassifier', '--indel-classifier',  type=str, help='action for each somaticseq.cmd')
    parser.add_argument('-trueSnv',         '--truth-snv',         type=str, help='VCF of true hits')
    parser.add_argument('-trueIndel',       '--truth-indel',       type=str, help='VCF of true hits')

    parser.add_argument('--mutect2-arguments',            type=str, help='extra parameters for Mutect2',                   default='')
    parser.add_argument('--mutect2-filter-arguments',     type=str, help='extra parameters for FilterMutectCalls step',    default='')
    parser.add_argument('--varscan-arguments',            type=str, help='extra parameters for VarScan2',                  default='')
    parser.add_argument('--varscan-pileup-arguments',     type=str, help='extra parameters for mpileup used for VarScan2', default='')
    parser.add_argument('--vardict-arguments',            type=str, help='extra parameters for VarDict',                   default='')
    parser.add_argument('--lofreq-arguments',             type=str, help='extra parameters for LoFreq',                    default='')
    parser.add_argument('--scalpel-discovery-arguments',  type=str, help='extra parameters for Scalpel discovery',         default='')
    parser.add_argument('--scalpel-export-arguments',     type=str, help='extra parameters for Scalpel export',            default='')
    parser.add_argument('--strelka-config-arguments',     type=str, help='extra parameters for Strelka2 config',           default='')
    parser.add_argument('--strelka-run-arguments',        type=str, help='extra parameters for Strelka2 run',              default='')
    parser.add_argument('--somaticseq-arguments',         type=str, help='extra parameters for SomaticSeq',                default='')
    
    parser.add_argument('-exome', '--exome-setting',  action='store_true', help='Invokes exome setting in Strelka2 and MuSE')

    parser.add_argument('-nt',        '--threads',        type=int, help='Split the input regions into this many threads', default=1)

    # Parse the arguments:
    args = parser.parse_args()
    workflowArguments = vars(args)

    workflowArguments['reference_dict'] = re.sub(r'\.[a-zA-Z]+$', '', workflowArguments['genome_reference'] ) + '.dict'

    return workflowArguments




def run_MuTect2(input_parameters, mem=8, nt=4, outvcf='MuTect2.vcf'):
    
    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'mutect2.{}.cmd'.format(ts)

    with open(outfile, 'w') as out:

        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )



        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode



def run_VarScan2(input_parameters, mem=4, minVAF=0.10, minMQ=25, minBQ=20, outvcf='VarScan2.vcf'):
    
    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'varscan2.{}.cmd'.format(ts)
    outname        = re.sub(r'\.[a-zA-Z]+$', '', outvcf )

    if input_parameters['minimum_VAF']:
        minVAF = input_parameters['minimum_VAF']

    selector_text  = '-l /mnt/{}'.format(input_parameters['inclusion_region']) if input_parameters['inclusion_region'] else ''

    with open(outfile, 'w') as out:
        
        out.write( "#!/bin/bash\n" )
        out.write( '\n' )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )

        out.write( 'docker run --rm -u $UID -v /:/mnt --memory {MEM}G lethalfang/samtools:1.7 bash -c \\\n'.format(MEM=mem) )
        out.write( '"samtools mpileup \\\n' )
        out.write( '-B -q {minMQ} -Q {minBQ} {extra_pileup_arguments} {selector_text} -f \\\n'.format(minMQ=minMQ, minBQ=minBQ, extra_pileup_arguments=input_parameters['varscan_pileup_arguments'], selector_text=selector_text) )
        out.write( '/mnt/{HUMAN_REFERENCE} \\\n'.format(HUMAN_REFERENCE=input_parameters['genome_reference']) )
        out.write( '/mnt/{NBAM} \\\n'.format(NBAM=input_parameters['normal_bam']) )
        out.write( '> /mnt/{OUTDIR}/normal.pileup"\n\n'.format(OUTDIR=input_parameters['output_directory']) )



        out.write( 'rm {OUTDIR}/tumor.pileup\n'.format(OUTDIR=input_parameters['output_directory']) )
        out.write( '\n' )
        
        
    
        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
    
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode





def run_VarDict(input_parameters, mem=14, minVAF=0.05, outvcf='VarDict.vcf'):
    
    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'vardict.{}.cmd'.format(ts)
    
    if input_parameters['minimum_VAF']:
        minVAF = input_parameters['minimum_VAF']

    total_bases = 0
    num_lines   = 0

    if input_parameters['inclusion_region']:
        bed_file = input_parameters['inclusion_region']
        
        with open(bed_file) as bed:
            line_i = bed.readline().rstrip()
            while line_i.startswith('track'):
                line_i = bed.readline().rstrip()
            while line_i:
                item = line_i.rstrip().split('\t')
                total_bases = total_bases + int(item[2]) - int(item[1])
                num_lines += 1
                line_i = bed.readline().rstrip()
    else:
        fai_file = input_parameters['genome_reference'] + '.fai'
        bed_file = '{}/{}'.format(input_parameters['output_directory'], 'genome.bed')
        
        with open(fai_file) as fai, open(bed_file, 'w') as wgs_bed:
            for line_i in fai:
                
                item = line_i.split('\t')
                
                total_bases += int( item[1] )
                num_lines   += 1
                
                wgs_bed.write( '{}\t{}\t{}\n'.format(item[0], '0', item[1]) )
    
    with open(outfile, 'w') as out:

        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )

        # Decide if Bed file needs to be "split" such that each line has a small enough region
        if total_bases/num_lines > 50000:
            out.write( 'docker run --rm -v /:/mnt -u $UID --memory {MEM}G lethalfang/somaticseq:{VERSION} \\\n'.format(MEM=mem, VERSION='latest') )
            out.write( '/opt/somaticseq/utilities/split_mergedBed.py \\\n' )
            out.write( '-infile /mnt/{SELECTOR} -outfile /mnt/{OUTDIR}/split_regions.bed\n\n'.format(SELECTOR=bed_file, OUTDIR=input_parameters['output_directory']) )

            bed_file = '{OUTDIR}/split_regions.bed'.format( OUTDIR=input_parameters['output_directory'] )





        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode




def run_LoFreq(input_parameters, mem=12, vcfprefix='LoFreq'):
    
    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'lofreq.{}.cmd'.format(ts)
    
    dbsnp_gz       = os.path.basename(input_parameters['dbsnp_vcf']) + '.gz'
    
    with open(outfile, 'w') as out:

        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )



        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode



def run_Scalpel(input_parameters, mem=16, outvcf='Scalpel.vcf'):
    
    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'scalpel.{}.cmd'.format(ts)
    
    twoPassFlag    = '--two-pass' if input_parameters['scalpel_two_pass'] else ''
    
    with open(outfile, 'w') as out:

        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )



        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode



def run_Strelka2(input_parameters, mem=4, outdirname='Strelka'):

    logdir         = input_parameters['output_directory'] + os.sep + 'logs'
    outfile        = logdir + os.sep + 'strelka.{}.cmd'.format(ts)
    
    exomeFlag = '--exome' if input_parameters['exome_setting'] else ''
    bed_gz = os.path.basename(input_parameters['inclusion_region']) + '.gz'
    
    with open(outfile, 'w') as out:

        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )


        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode



def run_SomaticSeq(input_parameters, mem=16):
    
    outdir         = input_parameters['output_directory'] + os.sep + input_parameters['somaticseq_directory']
    logdir         = outdir + os.sep + 'logs'
    outfile        = logdir + os.sep + 'somaticSeq.{}.cmd'.format(ts)
    
    trainFlag       = '--somaticseq-train'                                                 if input_parameters['train_somaticseq'] else ''
    inclusion       = '--inclusion-region {}'.format(input_parameters['inclusion_region']) if input_parameters['inclusion_region'] else ''
    exclusion       = '--exclusion-region {}'.format(input_parameters['exclusion_region']) if input_parameters['exclusion_region'] else ''
    cosmic          = '--cosmic-vcf {}'.format(input_parameters['cosmic_vcf'])             if input_parameters['cosmic_vcf']       else ''
    dbsnp           = '--dbsnp-vcf {}'.format(input_parameters['dbsnp_vcf'])               if input_parameters['dbsnp_vcf']        else ''
    snvClassifier   = '--classifier-snv {}'.format(input_parameters['snv_classifier'])     if input_parameters['snv_classifier']   else ''
    indelClassifier = '--classifier-indel {}'.format(input_parameters['indel_classifier']) if input_parameters['indel_classifier'] else ''
    trueSnvs        = '--truth-snv {}'.format(input_parameters['truth_snv'])               if input_parameters['truth_snv']        else ''
    trueIndels      = '--truth-indel {}'.format(input_parameters['truth_indel'])           if input_parameters['truth_indel']      else ''
    
    mutect2       = '{}/MuTect2.vcf'.format(input_parameters['output_directory'])                                    if input_parameters['run_mutect2'] else ''
    varscan_snv   = '{}/VarScan2.snp.vcf'.format(input_parameters['output_directory'])                               if input_parameters['run_varscan2'] else ''
    varscan_indel = '{}/VarScan2.indel.vcf'.format(input_parameters['output_directory'])                             if input_parameters['run_varscan2'] else ''
    jsm2          = '{}/JointSNVMix2.vcf'.format(input_parameters['output_directory'])                               if input_parameters['run_jointsnvmix2'] else ''
    sniper        = '{}/SomaticSniper.vcf'.format(input_parameters['output_directory'])                              if input_parameters['run_somaticsniper'] else ''
    vardict       = '{}/VarDict.vcf'.format(input_parameters['output_directory'])                                    if input_parameters['run_vardict'] else ''
    muse          = '{}/MuSE.vcf'.format(input_parameters['output_directory'])                                       if input_parameters['run_muse'] else ''
    lofreq_snv    = '{}/LoFreq.somatic_final.snvs.vcf.gz'.format(input_parameters['output_directory'])               if input_parameters['run_lofreq'] else ''
    lofreq_indel  = '{}/LoFreq.somatic_final.indels.vcf.gz'.format(input_parameters['output_directory'])             if input_parameters['run_lofreq'] else ''
    scalpel       = '{}/Scalpel.vcf'.format(input_parameters['output_directory'])                                    if input_parameters['run_scalpel'] else ''
    strelka_snv   = '{}/Strelka/results/variants/somatic.snvs.vcf.gz'.format(input_parameters['output_directory'])   if input_parameters['run_strelka2'] else ''
    strelka_indel = '{}/Strelka/results/variants/somatic.indels.vcf.gz'.format(input_parameters['output_directory']) if input_parameters['run_strelka2'] else ''
    
    os.makedirs(logdir, exist_ok=True)
    with open(outfile, 'w') as out:
        
        out.write( "#!/bin/bash\n\n" )
        
        out.write( '#$ -o {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -e {LOGDIR}\n'.format(LOGDIR=logdir) )
        out.write( '#$ -S /bin/bash\n' )
        out.write( '#$ -l h_vmem={}G\n'.format(mem) )
        out.write( 'set -e\n\n' )
        
        out.write( 'echo -e "Start at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n\n' )

        out.write( 'docker run --rm -v /:/mnt -u $UID --memory {MEM}g lethalfang/somaticseq:{VERSION} \\\n'.format(MEM=mem, VERSION=VERSION) )
        out.write( '/opt/somaticseq/somaticseq/run_somaticseq.py \\\n' )
        out.write( '{TRAIN} \\\n'.format(TRAIN=trainFlag) )
        out.write( '--output-directory /mnt/{OUTDIR} \\\n'.format(OUTDIR=outdir) )
        out.write( '--genome-reference /mnt/{HUMAN_REFERENCE} \\\n'.format(HUMAN_REFERENCE=input_parameters['genome_reference']) )
        out.write( '{INCLUSION} \\\n'.format(INCLUSION=inclusion) )
        out.write( '{EXCLUSION} \\\n'.format(EXCLUSION=exclusion) )
        out.write( '{COSMIC} \\\n'.format(COSMIC=cosmic) )
        out.write( '{DBSNP} \\\n'.format(DBSNP=dbsnp) )
        out.write( '{SNV_CLASSIFIER} \\\n'.format(SNV_CLASSIFIER=snvClassifier) )
        out.write( '{INDEL_CLASSIFIER} \\\n'.format(INDEL_CLASSIFIER=indelClassifier) )
        out.write( '{TRUE_SNV} \\\n'.format(TRUE_SNV=trueSnvs) )
        out.write( '{TRUE_INDEL} \\\n'.format(TRUE_INDEL=trueIndels) )
        out.write( '{EXTRA_ARGS} \\\n'.format(EXTRA_ARGS=input_parameters['somaticseq_arguments']) )
        out.write( 'paired \\\n' )
        out.write( '--tumor-bam-file  /mnt/{TBAM} \\\n'.format(TBAM=input_parameters['tumor_bam']) )
        out.write( '--normal-bam-file  /mnt/{NBAM} \\\n'.format(NBAM=input_parameters['normal_bam']) )
        out.write( '{MUTECT2} \\\n'.format(MUTECT2=mutect2) )
        out.write( '{VARSCAN_SNV} \\\n'.format(VARSCAN_SNV=varscan_snv) )
        out.write( '{VARSCAN_INDEL} \\\n'.format(VARSCAN_INDEL=varscan_indel) )
        out.write( '{JSM} \\\n'.format(JSM=jsm2) )
        out.write( '{SNIPER} \\\n'.format(SNIPER=sniper) )
        out.write( '{VARDICT} \\\n'.format(VARDICT=vardict) )
        out.write( '{MUSE} \\\n'.format(MUSE=muse) )
        out.write( '{LOFREQ_SNV} \\\n'.format(LOFREQ_SNV=lofreq_snv) )
        out.write( '{LOFREQ_INDEL} \\\n'.format(LOFREQ_INDEL=lofreq_indel) )
        out.write( '{SCALPEL} \\\n'.format(SCALPEL=scalpel) )
        out.write( '{STRELKA2_SNV} \\\n'.format(STRELKA2_SNV=strelka_snv) )
        out.write( '{STRELKA2_INDEL}\n'.format(STRELKA2_INDEL=strelka_indel) )

        out.write( '\necho -e "Done at `date +"%Y/%m/%d %H:%M:%S"`" 1>&2\n' )
        
    returnCode = os.system('{} {}'.format(input_parameters['action'], outfile) )

    return returnCode



##########################################################

if __name__ == '__main__':
    
    workflowArguments = run()
    
    if workflowArguments['inclusion_region']:
        bed_file = workflowArguments['inclusion_region']
        
    else:
        split_bed.fai2bed(workflowArguments['genome_reference'] + '.fai', workflowArguments['output_directory'] + os.sep + 'genome.bed')
        bed_file = workflowArguments['output_directory'] + os.sep + 'genome.bed'
    
    split_bed.split(bed_file, workflowArguments['output_directory'] + os.sep + 'bed', workflowArguments['threads'])

    os.makedirs(workflowArguments['output_directory'] + os.sep + 'logs', exist_ok=True)
    
        
    for thread_i in range(1, workflowArguments['threads']+1):
        
        if workflowArguments['threads'] > 1:
            
            perThreadParameter = copy(workflowArguments)
            
            # Add OUTDIR/thread_i for each thread
            perThreadParameter['output_directory'] = workflowArguments['output_directory'] + os.sep + str(thread_i)
            perThreadParameter['inclusion_region'] = '{}/{}.bed'.format( perThreadParameter['output_directory'], str(thread_i) )
            
            os.makedirs(perThreadParameter['output_directory'] + os.sep + 'logs', exist_ok=True)
            
            # Move 1.bed, 2.bed, ..., n.bed to each thread's subdirectory
            move('{}/{}.bed'.format(workflowArguments['output_directory'], thread_i), '{}/{}.bed'.format(perThreadParameter['output_directory'], thread_i) )
        
        else:
            perThreadParameter = copy(workflowArguments)
            perThreadParameter['inclusion_region'] = bed_file
        
        # Invoke parallelizable callers one by one:
        if workflowArguments['run_mutect2']:
            run_MuTect2( perThreadParameter )
            
        if workflowArguments['run_varscan2']:
            run_VarScan2( perThreadParameter )
            
        if workflowArguments['run_vardict']:
            run_VarDict( perThreadParameter )

        if workflowArguments['run_lofreq']:
            run_LoFreq( perThreadParameter )

        if workflowArguments['run_scalpel']:
            run_Scalpel( perThreadParameter )

        if workflowArguments['run_strelka2']:
            run_Strelka2( perThreadParameter )

        if workflowArguments['run_somaticseq']:
            run_SomaticSeq( perThreadParameter )
