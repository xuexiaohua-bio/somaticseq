#!/usr/bin/env python3

# python3 SSeq_merged.vcf2tsv.py -myvcf BINA.snp.vcf -samN snp_positions.normal.noindel.vcf.gz -samT snp_positions.tumor.noindel.5bpflank.vcf.gz -haploN haplo_N/merged.noindel.vcf.gz -haploT haplo_T/merged.noindel.vcf.gz -sniper somaticsniper/variants.vcf -varscan varscan2/variants.snp.vcf -jsm jointsnvmix2/variants.vcf -vardict vardict/variants.snp.vcf.gz -fai human_g1k_v37_decoy.fasta.fai -outfile SSeq2.snp.tsv

# Nothing from MuTect VCF is extracted because nothing from that file is useful here. 

# Input VCF can either be .vcf or .vcf.gz. 

import sys, argparse, math, gzip
import regex as re

sys.path.append('/net/kodiak/volumes/lake/shared/opt/Bina_SomaticMerge')
import genomic_file_handlers as genome


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-myvcf',   '--vcf-file', type=str, help='My VCF', required=True, default=None)

parser.add_argument('-samN',    '--samtools-normal-vcf-file', type=str, help='Normal VCF File', required=True, default=None)
parser.add_argument('-samT',    '--samtools-tumor-vcf-file', type=str, help='Tumor VCF File', required=True, default=None)
parser.add_argument('-haploN',  '--haplo-normal-vcf-file', type=str, help='Normal VCF File', required=True, default=None)
parser.add_argument('-haploT',  '--haplo-tumor-vcf-file', type=str, help='Tumor VCF File', required=True, default=None)

parser.add_argument('-mutect',  '--mutect-vcf', type=str, help='MuTect VCF. Just a place holder for now because no information from MuTect\'s VCF is used.', required=False, default=None)
parser.add_argument('-sniper',  '--somaticsniper-vcf', type=str, help='SomaticSniper VCF', required=False, default=None)
parser.add_argument('-varscan', '--varscan-vcf', type=str, help='VarScan2 VCF', required=False, default=None)
parser.add_argument('-jsm',     '--jsm-vcf', type=str, help='JointSNVMix2 VCF', required=False, default=None)
parser.add_argument('-vardict', '--vardict-vcf', type=str, help='VarDict VCF', required=False, default=None)

parser.add_argument('-fai',     '--reference-fasta-fai', type=str, help='Use the fasta.fai file to get the valid contigs', required=False, default=None)
parser.add_argument('-dict',    '--reference-fasta-dict', type=str, help='Use the reference dict file to get the valid contigs', required=False, default=None)
parser.add_argument('-scale',   '--p-scale', type=str, help='phred, fraction, or none', required=False, default=None)

parser.add_argument('-outfile', '--output-tsv-file', type=str, help='Output TSV Name', required=False, default='/dev/stdout')

args = parser.parse_args()

# Rename input:
myvcf     = args.vcf_file

samN      = args.samtools_normal_vcf_file
samT      = args.samtools_tumor_vcf_file
haploN    = args.haplo_normal_vcf_file
haploT    = args.haplo_tumor_vcf_file
mutectv   = args.mutect_vcf if args.mutect_vcf else '/dev/null'
sniperv   = args.somaticsniper_vcf if args.somaticsniper_vcf else '/dev/null'
varscanv  = args.varscan_vcf if args.varscan_vcf else '/dev/null'
jsmv      = args.jsm_vcf if args.jsm_vcf else '/dev/null'
vardictv  = args.vardict_vcf if args.vardict_vcf else '/dev/null'

fai_file  = args.reference_fasta_fai
dict_file = args.reference_fasta_dict
outfile   = args.output_tsv_file
p_scale   = args.p_scale


if p_scale == None:
    print('NO RE-SCALING', file=sys.stderr)
elif p_scale.lower() == 'phred':
    p_scale = 'phred'
elif p_scale.lower() == 'fraction':
    p_scale = 'fraction'
else:
    print('NO RE-SCALING', file=sys.stderr)
    p_scale = None



# Convert contig_sequence to chrom_seq dict:

if dict_file:
    chrom_seq = genome.faiordict2contigorder(dict_file, 'dict')
elif fai_file:
    chrom_seq = genome.faiordict2contigorder(fai_file, 'fai')
else:
    raise Exception('I need a fai or dict file, or else I do not know the contig order.')




nan = float('nan')
inf = float('inf')

# Normal/Tumor index in the Merged VCF file:
idxN,idxT = 0,1

# Normal/Tumor index in VarDict VCF
vdT,vdN = 0,1

pattern_chr_position = genome.pattern_chr_position


## Define functions:
def rescale(x, original=None, rescale_to=p_scale, max_phred=1001):
    if ( rescale_to == None ) or ( original.lower() == rescale_to.lower() ):
        y = x if isinstance(x, int) else '%.2f' % x
    elif original.lower() == 'fraction' and rescale_to == 'phred':
        y = genome.p2phred(x, max_phred=max_phred)
        y = '%.2f' % y
    elif original.lower() == 'phred' and rescale_to == 'fraction':
        y = genome.phred2p(x)
        y = '%.2f' % y
    return y
    


##### Extract information from external vcf files:
##### From Samtools vcf:
def sam_info_DP4(vcf_object):
    dp4_string = vcf_object.get_info_value('DP4')
    if dp4_string:
        dp4_string = dp4_string.split(',')
        dp4 = ( int(dp4_string[0]), int(dp4_string[1]), int(dp4_string[2]), int(dp4_string[3]) )
    else:
        dp4 = nan,nan,nan,nan
        
    return dp4
    


def sam_info_DP(vcf_object):
    result = vcf_object.get_info_value('DP')
    if result:
        return eval(result)
    else:
        return nan
    


def sam_info_MQ(vcf_object):
    result = vcf_object.get_info_value('MQ')
    if result:
        return eval(result)
    else:
        return nan



def sam_info_PV4(vcf_object):
    '''P-values for strand bias, baseQ bias, mapQ bias and tail distance bias'''
    pv4_string = vcf_object.get_info_value('PV4')
    if pv4_string:
        pv4_string = pv4_string.split(',')
        pv4 = ( float(pv4_string[0]), float(pv4_string[1]), float(pv4_string[2]), float(pv4_string[3]) )
    else:
        pv4 = nan,nan,nan,nan
    
    return pv4
    


##### From Haplotype caller vcf:
def haplo_MQ0(vcf_object):
    '''Total Mapping Quality Zero Reads'''
    
    mq0 = vcf_object.get_info_value('MQ0')
    if mq0:
        mq0 = eval(mq0)
    else:
        mq0 = nan
        
    return mq0



def haplo_MQ(vcf_object):
    '''RMS Mapping Quality'''
    result = vcf_object.get_info_value('MQ')
    if result:
        return eval(result)
    else:
        return nan
    
    
    
def haplo_MLEAF(vcf_object):
    '''Maximum likelihood expectation (MLE) for the allele frequency (not necessarily the same as the AF), for each ALT allele, in the same order as listed'''
    
    mleaf = vcf_object.get_info_value('MLEAF')
    
    if mleaf:
        mleaf = mleaf.split(',')
        mleaf = [eval(i) for i in mleaf]
        mleaf = max(mleaf)
        
    else:
        mleaf = nan
        
    return mleaf
    
    
    
def haplo_MLEAC(vcf_object):
    '''Maximum likelihood expectation (MLE) for the allele counts (not necessarily the same as the AC), for each ALT allele, in the same order as listed'''
    
    mleac = vcf_object.get_info_value('MLEAC')
    
    if mleac:        
        mleac = mleac.split(',')
        mleac = [eval(i) for i in mleac]
        mleac = max(mleac)
        
    else:
        mleac = nan
        
    return mleac



def haplo_DP(vcf_object):
    result = vcf_object.get_sample_value('DP')
    if result:
        return eval(result)
    else:
        return nan


def haplo_BaseQRankSum(vcf_object):
    '''Z-score from Wilcoxon rank sum test of Alt Vs. Ref base qualities'''
    result = vcf_object.get_info_value('BaseQRankSum')
    return eval(result) if result else nan
    
    
def haplo_ClippingRankSum(vcf_object):
    '''Z-score From Wilcoxon rank sum test of Alt vs. Ref number of hard clipped bases'''
    result = vcf_object.get_info_value('ClippingRankSum')
    return eval(result) if result else nan
    
    
def haplo_LikelihoodRankSum(vcf_object):
    '''Z-score from Wilcoxon rank sum test of Alt Vs. Ref haplotype likelihoods'''
    result = vcf_object.get_info_value('LikelihoodRankSum')
    return eval(result) if result else nan
    
    
def haplo_ReadPosRankSum(vcf_object):
    '''Z-score from Wilcoxon rank sum test of Alt vs. Ref read position bias'''
    result = vcf_object.get_info_value('ReadPosRankSum')
    return eval(result) if result else nan
    
    
def haplo_MQRankSum(vcf_object):
    '''Z-score From Wilcoxon rank sum test of Alt vs. Ref read mapping qualities'''
    result = vcf_object.get_info_value('MQRankSum')
    return eval(result) if result else nan



##### Stuff from my own vcf:
def calculate_baf(caf_string):
    pattern_CAF = re.compile(r'\[[0-9.,]+\]')
    caf = re.search(pattern_CAF, caf_string)
    if caf:
        caf_match = re.sub(r'\.([^0-9])', r'0\g<1>', caf.group())
        caf = eval(caf_match)
        caf.sort()
        baf = sum(caf[0:-1])  # Minor Allele Frequency
        
    return baf

  

def find_AMQ(vcf_object, i):
    amq = vcf_object.get_sample_value('AMQ', idx=i)
    
    if amq:
        amq = amq.split(',')
        amq_ref = eval(amq[0])
        try:
            amq_alt = eval(amq[1])
        except IndexError:
            amq_alt = nan
    
    else:
        amq_ref, amq_alt = nan, nan
        
    return amq_ref, amq_alt



def find_BQ(vcf_object, i):
    bq = vcf_object.get_sample_value('BQ', idx=i)
    # If there are two numbers, it came from SomaticSniper. If there is one number, it came from MuTect. 
    
    if bq:
        
        if bq == '.':
            bq_ref, bq_alt = nan, nan
            
        elif ',' in bq:
            bq = bq.split(',')
            bq_ref = eval(bq[0])
            bq_alt = eval(bq[1])
            
        else:
            bq_ref, bq_alt = eval(bq), eval(bq)
            
    else:
        bq_ref, bq_alt = nan, nan
        
    return bq_ref, bq_alt
    
    

def find_SOR(vcf_object):
    # VarDict's odd ratio, could be Inf, but other than Inf max was 180, so I will convert Inf --> 200. Stored in the TUMOR sample. 
    
    sor = vcf_object.get_info_value('SOR')
    if sor:
        sor = float(sor) if sor != 'Inf' else 200
    else:
        sor = nan
        
    return sor
    


def find_MSI(vcf_object):
    
    msi = vcf_object.get_info_value('MSI')
    if msi:
        msi = float(msi)
    else:
        msi = nan
    return msi
    
    
    
def find_MSILEN(vcf_object):
    
    msilen = vcf_object.get_info_value('MSILEN')
    if msilen:
        msilen = float(msilen)
    else:
        msilen = nan
    return msilen



def find_SHIFT3(vcf_object):
    
    shift3 = vcf_object.get_info_value('SHIFT3')
    if shift3:
        shift3 = float(shift3)
    else:
        shift3 = nan
    return shift3





# Header for the output data, created here so I won't have to indent this line:
out_header = \
'{CHROM}\t\
{POS}\t\
{ID}\t\
{REF}\t\
{ALT}\t\
{if_MuTect}\t\
{if_VarScan2}\t\
{if_JointSNVMix2}\t\
{if_SomaticSniper}\t\
{if_VarDict}\t\
{VarScan2_Score}\t\
{SNVMix2_Score}\t\
{Sniper_Score}\t\
{VarDict_Score}\t\
{if_dbsnp}\t\
{BAF}\t\
{COMMON}\t\
{G5}\t\
{G5A}\t\
{N_AMQ_REF}\t\
{N_AMQ_ALT}\t\
{N_BQ_REF}\t\
{N_BQ_ALT}\t\
{N_VAQ}\t\
{N_DP}\t\
{N_REF_FOR}\t\
{N_REF_REV}\t\
{N_ALT_FOR}\t\
{N_ALT_REV}\t\
{N_MQ}\t\
{N_NM}\t\
{N_PMEAN}\t\
{N_QSTD}\t\
{N_PSTD}\t\
{N_VQUAL}\t\
{N_StrandBias}\t\
{N_BaseQBias}\t\
{N_MapQBias}\t\
{N_TailDistBias}\t\
{N_MQ0}\t\
{N_MLEAC}\t\
{N_MLEAF}\t\
{N_BaseQRankSum}\t\
{N_ClippingRankSum}\t\
{N_LikelihoodRankSum}\t\
{N_ReadPosRankSum}\t\
{N_MQRankSum}\t\
{T_AMQ_REF}\t\
{T_AMQ_ALT}\t\
{T_BQ_REF}\t\
{T_BQ_ALT}\t\
{T_VAQ}\t\
{SOR}\t\
{MSI}\t\
{MSILEN}\t\
{SHIFT3}\t\
{MaxHomopolymer_Length}\t\
{SiteHomopolymer_Length}\t\
{T_DP}\t\
{T_REF_FOR}\t\
{T_REF_REV}\t\
{T_ALT_FOR}\t\
{T_ALT_REV}\t\
{T_MQ}\t\
{T_NM}\t\
{T_PMEAN}\t\
{T_QSTD}\t\
{T_PSTD}\t\
{T_VQUAL}\t\
{T_StrandBias}\t\
{T_BaseQBias}\t\
{T_MapQBias}\t\
{T_TailDistBias}\t\
{T_MQ0}\t\
{T_MLEAC}\t\
{T_MLEAF}\t\
{T_BaseQRankSum}\t\
{T_ClippingRankSum}\t\
{T_LikelihoodRankSum}\t\
{T_ReadPosRankSum}\t\
{T_MQRankSum}\t\
{InDel_Length}\t\
{TrueVariant_or_False}'




## Running
with genome.open_textfile(myvcf) as my_vcf, \
genome.open_textfile(samN) as samN, \
genome.open_textfile(samT) as samT, \
genome.open_textfile(haploN) as haploN, \
genome.open_textfile(haploT) as haploT, \
genome.open_textfile(mutectv) as mutect, \
genome.open_textfile(sniperv) as sniper, \
genome.open_textfile(varscanv) as varscan, \
genome.open_textfile(jsmv) as jsm, \
genome.open_textfile(vardictv) as vardict, \
open(outfile, 'w') as outhandle:
    
    
    my_line      = my_vcf.readline().rstrip()
    nsam_line    = samN.readline().rstrip()
    tsam_line    = samT.readline().rstrip()
    nhaplo_line  = haploN.readline().rstrip()
    thaplo_line  = haploT.readline().rstrip()
    mutect_line  = mutect.readline().rstrip()
    sniper_line  = sniper.readline().rstrip()
    varscan_line = varscan.readline().rstrip()
    jsm_line     = jsm.readline().rstrip()
    vardict_line = vardict.readline().rstrip()
    
    
    # Get through all the headers:
    while my_line.startswith('#'):
        my_line = my_vcf.readline().rstrip()
    
    while nsam_line.startswith('#'):
        nsam_line = samN.readline().rstrip()

    while tsam_line.startswith('#'):
        tsam_line = samT.readline().rstrip()

    while nhaplo_line.startswith('#'):
        nhaplo_line = haploN.readline().rstrip()

    while thaplo_line.startswith('#'):
        thaplo_line = haploT.readline().rstrip()
        
    while mutect_line.startswith('#'):
        mutect_line = mutect.readline().rstrip()

    while sniper_line.startswith('#'):
        sniper_line = sniper.readline().rstrip()

    while varscan_line.startswith('#'):
        varscan_line = varscan.readline().rstrip()

    while jsm_line.startswith('#'):
        jsm_line = jsm.readline().rstrip()

    while vardict_line.startswith('#'):
        vardict_line = vardict.readline().rstrip()
                    
    # First line:
    outhandle.write( out_header.replace('{','').replace('}','')  + '\n' )
    
    
    while my_line:
        
        my_coordinate = re.match( pattern_chr_position, my_line )
        if my_coordinate:
            my_coordinate = my_coordinate.group()
        else:
            print(my_line, file=sys.stderr)
            raise Exception('Coordinate does not match pattern.')
        
        ###################################################################################
        ############################ See what's in MY VCF line ############################
        my_vcfcall = genome.Vcf_line( my_line )
        
        # False Negatives are not a part of my original call:
        if 'FalseNegative' not in my_vcfcall.identifier:
            
            # If it's a "complex" variant (very rare), get me the first entry. 
            first_alt = my_vcfcall.altbase.split(',')[0]
        
            ### Somatic Callers:
            caller_positives = my_vcfcall.get_info_value('SOURCES')
            if caller_positives:
                callers = caller_positives.split(',')
                
                cga_positive           = 1 if 'CGA'           in callers else 0
                varscan2_positive      = 1 if 'VarScan2'      in callers else 0
                jointsnvmix2_positive  = 1 if 'JointSNVMix2'  in callers else 0
                somaticsniper_positive = 1 if 'SomaticSniper' in callers else 0
                vardict_positive       = 1 if 'VarDict'       in callers else 0
            
            else:
                cga_positive,varscan2_positive,jointsnvmix2_positive,somaticsniper_positive,vardict_positive = 0,0,0,0,0
                
                
            ### Calculate minor allele frequency (B Allele Frequency) in dbSNP data:
            caf = my_vcfcall.get_info_value('CAF')
            if caf:
                baf = calculate_baf(caf)
            else:
                baf = nan
                
                
            ### Is it in dbSNP:
            if re.search('rs[0-9]+', my_vcfcall.identifier):
                in_dbsnp = 1
            else:
                in_dbsnp = 0
                
            # Common SNP score:
            score_common_snp = 1 if my_vcfcall.get_info_value('COMMON') == '1' else 0
            g5 = 1 if my_vcfcall.get_info_value('G5') else 0
            g5a = 1 if my_vcfcall.get_info_value('G5A') else 0
            
    
            #####     #####     #####     #####     #####     #####
            if 'Correct' in my_vcfcall.identifier:
                judgement = 1
            elif 'FalsePositive' in my_vcfcall.identifier:
                judgement = 0
            else:
                judgement = nan
            #####     #####     #####     #####     #####     #####
            
            
            
            ############################################################################################
            ##################### Find the same coordinate in VarDict's VCF Output #####################
            if args.vardict_vcf:
                latest_vardict_run = genome.catchup(my_coordinate, vardict_line, vardict, chrom_seq)
                latest_vardict = genome.Vcf_line(latest_vardict_run[1])
                
                if latest_vardict_run[0]:
                    assert my_vcfcall.position == latest_vardict.position
                    
                    # Somatic Score:
                    if vardict_positive or ('Somatic' in latest_vardict.info):
                        score_vardict = latest_vardict.get_info_value('SSF')
                        score_vardict = float(score_vardict)
                        score_vardict = genome.p2phred(score_vardict, max_phred=100)
                    else:
                        score_vardict = nan


                    # SOR, MSI, MSILEN, and SHIFT3:
                    sor    = find_SOR(latest_vardict)
                    msi    = find_MSI(latest_vardict)
                    msilen = find_MSILEN(latest_vardict)
                    shift3 = find_SHIFT3(latest_vardict)

                    # Figure out the longest homopolymer length within the 41-bp region (20bp flank):
                    lseq = latest_vardict.get_info_value('LSEQ')
                    if lseq:
                        
                        # Longest homopolymer:
                        rseq = latest_vardict.get_info_value('RSEQ')
                        seq41_ref = lseq + latest_vardict.refbase + rseq
                        seq41_alt = lseq + first_alt + rseq
                        
                        ref_counts = genome.count_repeating_bases(seq41_ref)
                        alt_counts = genome.count_repeating_bases(seq41_alt)
                        
                        homopolymer_length = max( max(ref_counts), max(alt_counts) )
                        
                        # Homopolymer spanning the variant site:
                        site_homopolymer_left = re.search(r'[{}{}]+$'.format(latest_vardict.refbase, first_alt[0]), lseq)
                        if site_homopolymer_left:
                            site_homopolymer_left = site_homopolymer_left.group()
                        else:
                            site_homopolymer_left = ''
                        
                        site_homopolymer_right = re.match(r'{}+'.format(latest_vardict.refbase, first_alt[-1]), rseq)
                        if site_homopolymer_right:
                            site_homopolymer_right = site_homopolymer_right.group()
                        else:
                            site_homopolymer_right = ''
                        
                        site_homopolymer_ref = site_homopolymer_left + latest_vardict.refbase + site_homopolymer_right
                        site_homopolymer_alt = site_homopolymer_left + first_alt + site_homopolymer_right
                        
                        site_count_ref = genome.count_repeating_bases(site_homopolymer_ref)
                        site_count_alt = genome.count_repeating_bases(site_homopolymer_alt)
                        
                        site_homopolymer_length = max( max(site_count_ref), max(site_count_alt) )
                        
                            
                    else:
                        homopolymer_length      = nan
                        site_homopolymer_length = nan
            
                    
                    # Indel length:
                    indel_length = abs( len(first_alt) - len(latest_vardict.refbase) )
                    
                    
                    ## VarDict's sample info:
                    # Mean mismatch:
                    n_nm = latest_vardict.get_sample_value('NM', vdN)
                    try:
                        n_nm = eval(n_nm)
                    except TypeError:
                        n_nm = nan
                        
                    t_nm = latest_vardict.get_sample_value('NM', vdT)
                    try:
                        t_nm = eval(t_nm)
                    except TypeError:
                        t_nm = nan
                        
                    # Mean position in reads:
                    n_pmean = latest_vardict.get_sample_value('PMEAN', vdN)
                    try:
                        n_pmean = eval( n_pmean )
                    except TypeError:
                        n_pmean = nan
                        
                    t_pmean = latest_vardict.get_sample_value('PMEAN', vdT)
                    try:
                        t_pmean = eval( t_pmean )
                    except TypeError:
                        t_pmean = nan
                        
                    # Read Position STD
                    n_pstd = latest_vardict.get_sample_value('PSTD', vdN)
                    try:
                        n_pstd = eval(n_pstd)
                    except TypeError:
                        n_pstd = nan
                        
                    t_pstd = latest_vardict.get_sample_value('PSTD', vdT)
                    try:
                        t_pstd = eval( t_pstd )
                    except TypeError:
                        t_pstd = nan
                        
                    # Quality score STD in reads:
                    n_qstd = latest_vardict.get_sample_value('QSTD', vdN)
                    try:
                        n_qstd = eval( n_qstd )
                    except TypeError:
                        n_qstd = nan
                        
                    t_qstd = latest_vardict.get_sample_value('QSTD', vdT)
                    try:
                        t_qstd = eval( t_qstd )
                    except TypeError:
                        t_qstd = nan
                    
                    n_vqual = latest_vardict.get_sample_value('QUAL', vdN)
                    try:
                        n_vqual = eval( n_vqual )
                    except TypeError:
                        n_vqual = nan
                        
                    t_vqual = latest_vardict.get_sample_value('QUAL', vdT)
                    try:
                        t_vqual = eval( t_vqual )
                    except TypeError:
                        t_vqual = nan
        
        
                    # Reset the current line:
                    vardict_line = latest_vardict.vcf_line

            
            
                # The VarDict.vcf doesn't have this record, which doesn't make sense. It means wrong file supplied. 
                else:
                    sor = msi = msilen = shift3 = homopolymer_length = site_homopolymer_length = indel_length = n_nm = t_nm = n_pmean = t_pmean = n_pstd = t_pstd = n_qstd = t_qstd = n_vqual = t_vqual = score_vardict = nan
                    vardict_line = latest_vardict.vcf_line
                    
            else:
                
                sor = msi = msilen = shift3 = homopolymer_length = site_homopolymer_length = indel_length = n_nm = t_nm = n_pmean = t_pmean = n_pstd = t_pstd = n_qstd = t_qstd = n_vqual = t_vqual = score_vardict = nan
            
            
            
            ############################################################################################
            ##################### Find the same coordinate in SomaticSniper's VCF# #####################
            # SomaticSniper's SSC may be wiped out during CombineVariants, since I made VarDict take precedence. Use the extra sniper file if available:
            if args.somaticsniper_vcf:
                
                latest_sniper_run = genome.catchup(my_coordinate, sniper_line, sniper, chrom_seq)
                latest_sniper = genome.Vcf_line(latest_sniper_run[1])
                
                if latest_sniper_run[0]:
                    
                    assert my_vcfcall.position == latest_sniper.position
                    
                    # Somatic Score:
                    if somaticsniper_positive:
                        score_somaticsniper = latest_sniper.get_sample_value('SSC', 1)
                        score_somaticsniper = int(score_somaticsniper) if score_somaticsniper else nan
                    else:
                        score_somaticsniper = nan
                        
                    # Variant Allele Quality:
                    n_vaq = latest_sniper.get_sample_value('VAQ', idxN)
                    n_vaq = int(n_vaq) if n_vaq else nan
                    
                    t_vaq = latest_sniper.get_sample_value('VAQ', idxT)
                    t_vaq = int(t_vaq) if t_vaq else nan
                    
                    # Average base quality:
                    n_bq_ref, n_bq_alt = find_BQ(latest_sniper, idxN)
                    t_bq_ref, t_bq_alt = find_BQ(latest_sniper, idxT)
            
                    # Average mapping quality for each allele present in the genotype:
                    n_amq_ref, n_amq_alt = find_AMQ(latest_sniper, idxN)
                    t_amq_ref, t_amq_alt = find_AMQ(latest_sniper, idxT)
                    
                    # Reset the current line:
                    sniper_line = latest_sniper.vcf_line

                
                # The SomaticSniper.vcf doesn't have this record, which doesn't make sense. It means wrong file supplied. 
                else:
                    n_vaq = t_vaq = n_amq_ref = n_amq_alt = t_amq_ref = t_amq_alt = n_bq_ref = n_bq_alt = t_bq_ref = t_bq_alt = score_somaticsniper = nan
                    sniper_line = latest_sniper.vcf_line
                    
            else:
                
                n_vaq = t_vaq = n_amq_ref = n_amq_alt = t_amq_ref = t_amq_alt = n_bq_ref = n_bq_alt = t_bq_ref = t_bq_alt = score_somaticsniper = nan
            
            
            
            ############################################################################################
            ######################## Find the same coordinate in VarScan's VCF #########################
            if args.varscan_vcf:
                
                latest_varscan_run = genome.catchup(my_coordinate, varscan_line, varscan, chrom_seq)
                latest_varscan = genome.Vcf_line(latest_varscan_run[1])
                
                if latest_varscan_run[0]:
                    
                    assert my_vcfcall.position == latest_varscan.position
                    
                    # Somatic Score:
                    score_varscan2 = int(latest_varscan.get_info_value('SSC'))
                    
                    # Reset the current line:
                    varscan_line = latest_varscan.vcf_line

                
                # The VarScan.vcf doesn't have this record, which doesn't make sense. It means wrong file supplied. 
                else:
                    score_varscan2 = nan
                    varscan_line = latest_varscan.vcf_line
                    
            else:
                
                score_varscan2 = nan
            
            
            ############################################################################################
            ########################## Find the same coordinate in JSM's VCF# ##########################
            if args.jsm_vcf:
                
                latest_jsm_run = genome.catchup(my_coordinate, jsm_line, jsm, chrom_seq)
                latest_jsm = genome.Vcf_line(latest_jsm_run[1])
                
                if latest_jsm_run[0]:
                    
                    assert my_vcfcall.position == latest_jsm.position
                    
                    # Somatic Score:
                    aaab = float( latest_jsm.get_info_value('AAAB') )
                    aabb = float( latest_jsm.get_info_value('AABB') )
                    jointsnvmix2_p = 1 - aaab - aabb
                    score_jointsnvmix2 = genome.p2phred(jointsnvmix2_p, max_phred=50)
                    
                    # Reset the current line:
                    jsm_line = latest_jsm.vcf_line

                # The VarScan.vcf doesn't have this record, which doesn't make sense. It means wrong file supplied. 
                else:
                    score_jointsnvmix2 = nan
                    jsm_line = latest_jsm.vcf_line
                    
            else:
                
                score_jointsnvmix2 = nan
            
            
            
            ############################################################################################
            #################### Find the same coordinate in NORMAL vcf by SAMTOOLS ####################
            # Things to extract (if available): 
            # DP4, PV4 (strand bias, baseQ bias, mapQ bias, and tail distance bias), DP, and MQ
            
            latest_nsam_run = genome.catchup(my_coordinate, nsam_line, samN, chrom_seq)
            latest_samnormal = genome.Vcf_line(latest_nsam_run[1])
            
            # If the position exists in this samtools generated vcf file:
            if latest_nsam_run[0]:
                
                assert my_vcfcall.position == latest_samnormal.position
                
                # Normal samtools info extraction:
                N_ref_for,N_ref_rev,N_alt_for,N_alt_rev = sam_info_DP4(latest_samnormal)
                N_p_strandbias,N_p_baseQbias,N_p_mapQbias,N_p_taildisbias = sam_info_PV4(latest_samnormal)
                N_Sdp = latest_samnormal.get_info_value('DP')
                N_mq  = sam_info_MQ(latest_samnormal)
                                
                # Reset the current line:
                nsam_line = latest_samnormal.vcf_line
                
            # If the position does not exist in this vcf file, in which case the sam_vcf should have gone past the my_coordinate:
            else:
                
                #assert genome.whoisbehind([my_vcfcall.chromosome, my_vcfcall.position], [latest_samnormal.chromosome, latest_samnormal.position]) == 0
                nsam_line = latest_samnormal.vcf_line
                
                N_ref_for = N_ref_rev = N_alt_for = N_alt_rev = N_p_strandbias = N_p_baseQbias = N_p_mapQbias = N_p_taildisbias = N_Sdp = N_mq = nan
    
            
            
            #################### Find the same coordinate in NORMAL vcf by GATK Haplotype ####################
            # Things to extract (if available): 
            # DP, MQ, MQ0, MLEAC, MLEAF, BaseQRankSum, ClippingRankSum, LikelihoodRankSum, ReadPosRankSum, MQRankSum
            
            latest_nhaplo_run = genome.catchup(my_coordinate, nhaplo_line, haploN, chrom_seq)
            latest_haplonormal = genome.Vcf_line(latest_nhaplo_run[1])
            
            if latest_nhaplo_run[0]:
                assert my_vcfcall.position == latest_haplonormal.position
                                
                # Normal haplotype caller info extraction:
                N_mq0         = haplo_MQ0(latest_haplonormal)
                N_mleac       = haplo_MLEAC(latest_haplonormal)
                N_mleaf       = haplo_MLEAF(latest_haplonormal)
                N_baseQrank   = haplo_BaseQRankSum(latest_haplonormal)
                N_cliprank    = haplo_ClippingRankSum(latest_haplonormal)
                N_likelirank  = haplo_LikelihoodRankSum(latest_haplonormal)
                N_readposrank = haplo_ReadPosRankSum(latest_haplonormal)
                N_mqrank      = haplo_MQRankSum(latest_haplonormal)
                N_Hdp         = haplo_DP(latest_haplonormal)
                N_Hmq         = haplo_MQ(latest_haplonormal)
                
                # Reset the current line:
                nhaplo_line = latest_haplonormal.vcf_line
            
            else:
                #assert genome.whoisbehind([my_vcfcall.chromosome, my_vcfcall.position], [latest_haplonormal.chromosome, latest_haplonormal.position]) == 0
                nhaplo_line = latest_haplonormal.vcf_line
                                
                N_mq0 = N_mleac = N_mleaf = N_baseQrank = N_cliprank = N_likelirank = N_readposrank = N_mqrank = N_Hdp = N_Hmq = nan
            
            
            
            ###########################################################################################
            #################### Find the same coordinate in TUMOR vcf by SAMTOOLS ####################
            latest_tsam_run = genome.catchup(my_coordinate, tsam_line, samT, chrom_seq)
            latest_samtumor = genome.Vcf_line(latest_tsam_run[1])
            
            # If the position exists in this samtools generated vcf file:
            if latest_tsam_run[0]:
                assert my_vcfcall.position == latest_samtumor.position
                
                T_ref_for,T_ref_rev,T_alt_for,T_alt_rev = sam_info_DP4(latest_samtumor)
                T_p_strandbias,T_p_baseQbias,T_p_mapQbias,T_p_taildisbias = sam_info_PV4(latest_samtumor)
                T_Sdp  = latest_samtumor.get_info_value('DP')
                T_mq  = sam_info_MQ(latest_samtumor)
                
                # Reset the current line:
                tsam_line = latest_samtumor.vcf_line
            
            # If not:
            else:
                #assert genome.whoisbehind([my_vcfcall.chromosome, my_vcfcall.position], [latest_samtumor.chromosome, latest_samtumor.position]) == 0
                tsam_line = latest_samtumor.vcf_line
                
                T_ref_for = T_ref_rev = T_alt_for = T_alt_rev = T_p_strandbias = T_p_baseQbias = T_p_mapQbias = T_p_taildisbias = T_Sdp = T_mq = nan
                
            
            
            #################### Find the same coordinate in TUMOR vcf by GATK Haplotype ####################
            # Things to extract (if available): 
            # DP, MQ, MQ0, MLEAC, MLEAF, BaseQRankSum, ClippingRankSum, LikelihoodRankSum, ReadPosRankSum, MQRankSum

            latest_thaplo_run = genome.catchup(my_coordinate, thaplo_line, haploT, chrom_seq)
            latest_haplotumor = genome.Vcf_line(latest_thaplo_run[1])
            
            if latest_thaplo_run[0]:
                assert my_vcfcall.position == latest_haplotumor.position
                
                # Normal haplotype caller info extraction:
                T_mq0         = haplo_MQ0(latest_haplotumor)
                T_mleac       = haplo_MLEAC(latest_haplotumor)
                T_mleaf       = haplo_MLEAF(latest_haplotumor)
                T_baseQrank   = haplo_BaseQRankSum(latest_haplotumor)
                T_cliprank    = haplo_ClippingRankSum(latest_haplotumor)
                T_likelirank  = haplo_LikelihoodRankSum(latest_haplotumor)
                T_readposrank = haplo_ReadPosRankSum(latest_haplotumor)
                T_mqrank      = haplo_MQRankSum(latest_haplotumor)
                T_Hdp         = haplo_DP(latest_haplotumor)
                T_Hmq         = haplo_MQ(latest_haplotumor)
                
                # Reset the current line:
                thaplo_line = latest_haplotumor.vcf_line
            
            else:
                #assert genome.whoisbehind([my_vcfcall.chromosome, my_vcfcall.position], [latest_haplotumor.chromosome, latest_haplotumor.position]) == 0
                thaplo_line = latest_haplotumor.vcf_line
                
                T_mq0 = T_mleac = T_mleaf = T_baseQrank = T_cliprank = T_likelirank = T_readposrank = T_mqrank = T_Hdp = T_Hmq = nan

            
            
            ###
            if math.isnan(N_mq): N_mq = N_Hmq
            if math.isnan(T_mq): T_mq = T_Hmq
            
            
            if not math.isnan(N_Hdp):
                N_dp = N_Hdp
            else:
                N_dp = N_Sdp
            
            
            if not math.isnan(T_Hdp):
                T_dp = T_Hdp
            else:
                T_dp = T_Hdp
            
            
            ###
            out_line = out_header.format( \
            CHROM                   = my_vcfcall.chromosome,                                  \
            POS                     = my_vcfcall.position,                                    \
            ID                      = my_vcfcall.identifier,                                  \
            REF                     = my_vcfcall.refbase,                                     \
            ALT                     = my_vcfcall.altbase,                                     \
            if_MuTect               = cga_positive,                                           \
            if_VarScan2             = varscan2_positive,                                      \
            if_JointSNVMix2         = jointsnvmix2_positive,                                  \
            if_SomaticSniper        = somaticsniper_positive,                                 \
            if_VarDict              = vardict_positive,                                       \
            VarScan2_Score          = rescale(score_varscan2,      'phred', p_scale, 1001),   \
            SNVMix2_Score           = rescale(score_jointsnvmix2,  'phred', p_scale, 1001),   \
            Sniper_Score            = rescale(score_somaticsniper, 'phred', p_scale, 1001),   \
            VarDict_Score           = rescale(score_vardict,       'phred', p_scale, 1001),   \
            if_dbsnp                = in_dbsnp,                                               \
            BAF                     = rescale(baf, 'fraction', p_scale, 1001),                \
            COMMON                  = score_common_snp,                                       \
            G5                      = g5,                                                     \
            G5A                     = g5a,                                                    \
            N_AMQ_REF               = rescale(n_amq_ref, 'phred', p_scale, 1001),             \
            N_AMQ_ALT               = rescale(n_amq_alt, 'phred', p_scale, 1001),             \
            N_BQ_REF                = rescale(n_bq_ref,  'phred', p_scale, 1001),             \
            N_BQ_ALT                = rescale(n_bq_alt,  'phred', p_scale, 1001),             \
            N_VAQ                   = rescale(n_vaq,     'phred', p_scale, 1001),             \
            N_DP                    = N_dp,                                                   \
            N_REF_FOR               = N_ref_for,                                              \
            N_REF_REV               = N_ref_rev,                                              \
            N_ALT_FOR               = N_alt_for,                                              \
            N_ALT_REV               = N_alt_rev,                                              \
            N_MQ                    = N_mq,                                                   \
            N_NM                    = n_nm,                                                   \
            N_PMEAN                 = n_pmean,                                                \
            N_QSTD                  = n_qstd,                                                 \
            N_PSTD                  = n_pstd,                                                 \
            N_VQUAL                 = n_vqual,                                                \
            N_StrandBias            = rescale(N_p_strandbias,  'fraction', p_scale, 1001),    \
            N_BaseQBias             = rescale(N_p_baseQbias,   'fraction', p_scale, 1001),    \
            N_MapQBias              = rescale(N_p_mapQbias,    'fraction', p_scale, 1001),    \
            N_TailDistBias          = rescale(N_p_taildisbias, 'fraction', p_scale, 1001),    \
            N_MQ0                   = N_mq0,                                                  \
            N_MLEAC                 = N_mleac,                                                \
            N_MLEAF                 = N_mleaf,                                                \
            N_BaseQRankSum          = N_baseQrank,                                            \
            N_ClippingRankSum       = N_cliprank,                                             \
            N_LikelihoodRankSum     = N_likelirank,                                           \
            N_ReadPosRankSum        = N_readposrank,                                          \
            N_MQRankSum             = N_mqrank,                                               \
            T_AMQ_REF               = rescale(t_amq_ref, 'phred', p_scale, 1001),             \
            T_AMQ_ALT               = rescale(t_amq_alt, 'phred', p_scale, 1001),             \
            T_BQ_REF                = rescale(t_bq_ref,  'phred', p_scale, 1001),             \
            T_BQ_ALT                = rescale(t_bq_alt,  'phred', p_scale, 1001),             \
            T_VAQ                   = rescale(t_vaq,     'phred', p_scale, 1001),             \
            SOR                     = sor,                                                    \
            MSI                     = msi,                                                    \
            MSILEN                  = msilen,                                                 \
            SHIFT3                  = shift3,                                                 \
            MaxHomopolymer_Length   = homopolymer_length,                                     \
            SiteHomopolymer_Length  = site_homopolymer_length,                                \
            T_DP                    = T_dp,                                                   \
            T_REF_FOR               = T_ref_for,                                              \
            T_REF_REV               = T_ref_rev,                                              \
            T_ALT_FOR               = T_alt_for,                                              \
            T_ALT_REV               = T_alt_rev,                                              \
            T_MQ                    = T_mq,                                                   \
            T_NM                    = t_nm,                                                   \
            T_PMEAN                 = t_pmean,                                                \
            T_QSTD                  = t_qstd,                                                 \
            T_PSTD                  = t_pstd,                                                 \
            T_VQUAL                 = t_vqual,                                                \
            T_StrandBias            = rescale(T_p_strandbias,  'fraction', p_scale, 1001),    \
            T_BaseQBias             = rescale(T_p_baseQbias,   'fraction', p_scale, 1001),    \
            T_MapQBias              = rescale(T_p_mapQbias,    'fraction', p_scale, 1001),    \
            T_TailDistBias          = rescale(T_p_taildisbias, 'fraction', p_scale, 1001),    \
            T_MQ0                   = T_mq0,                                                  \
            T_MLEAC                 = T_mleac,                                                \
            T_MLEAF                 = T_mleaf,                                                \
            T_BaseQRankSum          = T_baseQrank,                                            \
            T_ClippingRankSum       = T_cliprank,                                             \
            T_LikelihoodRankSum     = T_likelirank,                                           \
            T_ReadPosRankSum        = T_readposrank,                                          \
            T_MQRankSum             = T_mqrank,                                               \
            InDel_Length            = indel_length,                                           \
            TrueVariant_or_False    = judgement )
            
            # Print it out to stdout:
            outhandle.write(out_line + '\n')
            
            
        # Read on:
        my_line = my_vcf.readline().rstrip()