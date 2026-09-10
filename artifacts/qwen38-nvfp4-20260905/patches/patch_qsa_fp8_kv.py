#!/usr/bin/env python3
"""Autorise un cache KV en fp8-e4m3 sur le QSA de Qwen3.8-Flash-Next (vLLM/NVIDIA).

CE QUE CE PATCH FAIT, ET CE QU'IL NE FAIT PAS
---------------------------------------------
vLLM a DEJA pose toute la plomberie de quantisation du cache pour cette couche :
`get_kv_cache_spec` transmet `kv_quant_mode`, `set_default_quant_scales` enregistre
`_k_scale`/`_v_scale`, l'allocation et l'ECRITURE passent par le chemin generique
du cœur. Le seul trou est la LECTURE : les noyaux Triton chargent le cache en
supposant du bf16, et cinq gardes refusent tout le reste plutot que de lire de
travers.

Ce patch ajoute la dequantisation a la lecture et leve les gardes. Il est INERTE
tant que `--kv-cache-dtype` vaut `auto`/`bfloat16` : `FP8_KV` est alors faux, la
branche de dequantisation est eliminee a la compilation Triton, et l'image se
comporte EXACTEMENT comme l'amont.

POURQUOI REMONTER EN BF16 ET NON EN FP32
-----------------------------------------
MiaAI-Lab, qui a fait le meme travail cote SGLang, remonte K/V en fp32 : « two QSA
paths upcast K/V loads to fp32 in-kernel (q stays bf16) », SM121 ne sachant pas
faire de `dot` en fp8. Remonter en bf16 coute deux fois moins de registres -- donc
une meilleure occupancy, ce qui compte sur un noyau memory-bound -- au prix d'un
arrondi supplementaire apres mise a l'echelle. PERSONNE n'a publie la comparaison
des deux. On commence par bf16 et on MESURE ; `QSA_FP8_UPCAST_FP32=1` bascule sur
l'autre variante sans rebuild pour pouvoir trancher.

CE QUI N'EST PAS COUVERT
------------------------
Le cache COMPRESSE lu par `_qsa_mqa_paged_kernel` (forme [pages, page_size, 1,
head_dim]) est distinct du cache KV principal ; rien ne garantit qu'il suive le
meme dtype. Il est patche par prudence, sous son propre drapeau : si son dtype ne
bouge pas, la branche reste morte et le noyau est inchange.

NVFP4 n'est pas traite ici : il ajoute un format packe et des echelles fp8
imbriquees. Le fp8-e4m3 valide d'abord la chaine complete.

VERIFICATION -- « ca demarre » ne prouve RIEN
---------------------------------------------
Le mode de defaillance a craindre est SILENCIEUX : le bug de `block_size` du
prefix caching, corrige le 2026-08-30, rendait des reponses plausibles et fausses
sans lever d'erreur. Utiliser `validation/capture_baseline.py` AVANT et
`validation/compare.py` APRES. Le test qui compte est l'egalite des JETONS, pas
l'absence de crash.

Usage :
    python3 patch_qsa_fp8_kv.py <site-packages>
"""
import ast
import sys

SP = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: patch_qsa_fp8_kv.py <site-packages>")
BASE = f"{SP}/vllm/models/qwen3_8_flash_next/nvidia"
OPS = f"{BASE}/ops/qsa.py"
OWNER = f"{BASE}/qsa.py"

# Variante de dequantisation. bf16 par defaut (registres, occupancy) ; fp32 pour
# reproduire le choix de MiaAI-Lab si la precision bf16 se revele insuffisante.
# Plus de variante fp32 : `_cast_kv_tile` redescend au dtype de la requete, et
# c'est le choix d'UPSTREAM VLLM lui-meme (`return (data.to(tl.float32) *
# tl.load(tensor_scale)).to(Q.dtype)`). MiaAI-Lab monte en fp32 cote SGLang ;
# suivre vLLM ici, c'est heriter de ses corrections plutot que d'en diverger.


def remplacer(texte: str, avant: str, apres: str, quoi: str) -> str:
    n = texte.count(avant)
    assert n == 1, f"ancre '{quoi}' vue {n} fois (attendu 1) -- l'amont a bouge"
    return texte.replace(avant, apres)


# ---------------------------------------------------------------- ops/qsa.py
ops = open(OPS).read()

# 0. REUTILISER la dequantisation canonique de vLLM plutot que d'en ecrire une
#    seconde. `_cast_kv_tile` (v1/attention/ops/triton_unified_attention.py) fait
#    deja exactement ce travail pour l'attention unifiee, gere les quatre modes
#    (NONE, FP8 per-tensor, INT8/FP8 per-token-head) ET le cas ou la requete est
#    elle-meme en fp8 -- que cette version-ci avait oublie. Dupliquer la formule
#    aurait cree une seconde verite qui derive : c'est precisement le defaut que
#    ce depot traque partout ailleurs.
ops = remplacer(ops,
    "from vllm.triton_utils import HAS_TRITON, tl, triton",
    "from vllm.triton_utils import HAS_TRITON, tl, triton\n"
    "from vllm.v1.attention.ops.triton_unified_attention import _cast_kv_tile",
    "import du helper canonique")

# 1. Noyau DECODE : signature. Les echelles sont des pointeurs (tenseurs 0-dim
#    cote Python) ; `FP8_KV` est une constexpr, donc la branche disparait a la
#    compilation quand elle est fausse.
ops = remplacer(ops,
    "    num_requests,\n    TOPK: tl.constexpr,",
    "    num_requests,\n"
    "    k_scale_ptr,\n"
    "    v_scale_ptr,\n"
    "    KV_QUANT_MODE: tl.constexpr,\n"
    "    TOPK: tl.constexpr,",
    "signature du noyau decode")

# 2. Noyau DECODE : dequantisation, entre le chargement et le produit scalaire.
#    `keys` est charge tel qu'il est stocke ; s'il est fp8, il vaut
#    quantise * echelle. On remonte, on met a l'echelle, on redescend au dtype de
#    la requete pour que `tl.dot` ait deux operandes de meme type.
ops = remplacer(ops,
    "        scores = tl.dot(query, keys)\n"
    "        # Scaling scores avoids re-quantizing a scaled query to BF16.",
    "        keys = _cast_kv_tile(keys, query, k_scale_ptr, KV_QUANT_MODE)\n"
    "        values = _cast_kv_tile(values, query, v_scale_ptr, KV_QUANT_MODE)\n"
    "        scores = tl.dot(query, keys)\n"
    "        # Scaling scores avoids re-quantizing a scaled query to BF16.",
    "dequantisation du noyau decode")

# 3. Noyau MQA (cache COMPRESSE, distinct du KV principal) : signature.
ops = remplacer(ops,
    "    score_divisor,\n    PAGE_SIZE: tl.constexpr,",
    "    score_divisor,\n"
    "    kc_scale_ptr,\n"
    "    KC_QUANT_MODE: tl.constexpr,\n"
    "    PAGE_SIZE: tl.constexpr,",
    "signature du noyau mqa")

# 4. Noyau MQA : dequantisation. Il ne lit que les cles (c'est le selecteur de
#    blocs), pas les valeurs.
ops = remplacer(ops,
    "        scores = tl.dot(keys, query, out_dtype=tl.float32)",
    "        keys = _cast_kv_tile(keys, query, kc_scale_ptr, KC_QUANT_MODE)\n"
    "        scores = tl.dot(keys, query, out_dtype=tl.float32)",
    "dequantisation du noyau mqa")

# 5. Le garde du wrapper decode. Il exigeait l'egalite des trois dtypes ; on
#    autorise un CACHE fp8 avec une REQUETE bf16, ce qui est precisement le point.
ops = remplacer(ops,
    "    assert q.dtype == k_cache.dtype == v_cache.dtype == torch.bfloat16",
    "    assert q.dtype == torch.bfloat16\n"
    "    assert k_cache.dtype == v_cache.dtype\n"
    "    _fp8_kv = k_cache.dtype == torch.float8_e4m3fn  # e5m2: the mqa launch has no quant mode for it\n"
    "    # 1 = FP8_PER_TENSOR in KVQuantMode. The per-token-head modes (2, 3)\n"
    "    # apply their scales elsewhere in the loop and are not wired here.\n"
    "    _kv_mode = 1 if _fp8_kv else 0\n"
    "    assert k_cache.dtype == torch.bfloat16 or _fp8_kv, (\n"
    '        f"QSA: KV cache is {k_cache.dtype}, expected bf16 or fp8_e4m3"\n'
    "    )",
    "garde de dtype du wrapper decode")

# 6. Passage des echelles au lancement du noyau decode. Absentes, on retombe sur
#    des echelles neutres : le patch reste alors un no-op numerique.
ops = remplacer(ops,
    "        block_table.shape[0],\n        TOPK=logical_indices.shape[1],",
    "        block_table.shape[0],\n"
    "        _k_scale_t,\n"
    "        _v_scale_t,\n"
    "        KV_QUANT_MODE=_kv_mode,\n"
    "        TOPK=logical_indices.shape[1],",
    "lancement du noyau decode")

# 7. Les tenseurs d'echelle, materialises juste avant le lancement.
ops = remplacer(ops,
    "    _qsa_sparse_paged_gqa_splitk_kernel[partial_grid](",
    "    _one = torch.ones((), dtype=torch.float32, device=q.device)\n"
    "    _k_scale_t = k_scale if k_scale is not None else _one\n"
    "    _v_scale_t = v_scale if v_scale is not None else _one\n"
    "    _qsa_sparse_paged_gqa_splitk_kernel[partial_grid](",
    "materialisation des echelles decode")

# 8. Signature publique du wrapper decode. Les echelles sont OPTIONNELLES : sans
#    elles, `_k_scale_t` retombe sur 1.0 et le patch est un no-op numerique, ce
#    qui garantit que tout appelant non modifie continue de fonctionner.
ops = remplacer(ops,
    "    token_to_req: torch.Tensor,\n"
    "    out: torch.Tensor | None = None,\n"
    ") -> torch.Tensor:",
    "    token_to_req: torch.Tensor,\n"
    "    out: torch.Tensor | None = None,\n"
    "    k_scale: torch.Tensor | None = None,\n"
    "    v_scale: torch.Tensor | None = None,\n"
    ") -> torch.Tensor:",
    "signature du wrapper decode")

# 19. LE CACHE DU SELECTEUR DE BLOCS, reinterpretation manquante.
#
# `qsa_mqa_paged` lit le cache de l'INDEXEUR (`self.indexer.raw_key_cache`), pas
# le cache KV principal. Ce cache-la suit aussi `kv_cache_dtype` et arrive donc en
# `uint8` -- non reinterprete, puisque le `.view()` de `forward_qsa` ne porte que
# sur le cache principal.
#
# Consequence, si on ne fait rien : `KC_QUANT_MODE` retombe a 0, le noyau lit des
# OCTETS comme des flottants, et la selection des blocs devient aberrante. Comme
# cette selection decide QUELS blocs l'attention va regarder, la sortie diverge
# des le PREMIER jeton -- exactement ce qui a ete mesure le 2026-08-30 (11 sorties
# sur 12 fausses, plusieurs au rang 0), alors meme que le chemin de decode etait
# correct de bout en bout.
ops = remplacer(ops,
    "    _validate_mqa(q)",
    "    # The block selector reads the indexer cache, a SEPARATE tensor from the\n"
    "    # main KV cache that follows the same dtype. Left as uint8 the kernel\n"
    "    # would read integers and pick arbitrary blocks.\n"
    "    if k_cache.dtype == torch.uint8:\n"
    "        k_cache = k_cache.view(torch.float8_e4m3fn)\n"
    "    _validate_mqa(q)",
    "reinterpretation du cache de l'indexeur")

# 9. Lancement du noyau mqa : echelle neutre tant que le cache compresse reste bf16.
ops = remplacer(ops,
    "        float(score_divisor),\n        PAGE_SIZE=k_cache.shape[1],",
    "        float(score_divisor),\n"
    "        torch.ones((), dtype=torch.float32, device=q.device),\n"
    "        1 if k_cache.dtype == torch.float8_e4m3fn else 0,\n"
    "        PAGE_SIZE=k_cache.shape[1],",
    "lancement du noyau mqa")

# 18. LA MEMOIRE PARTAGEE : reduire le bloc quand le cache est quantifie.
#
# `_cast_kv_tile` materialise une tuile fp32 (`data.to(tl.float32)`) avant de
# redescendre au dtype de la requete. Cette tuile est DEUX FOIS plus large que le
# bf16 d'origine, sur K et sur V. Mesure au boot :
#
#     triton.runtime.errors.OutOfResources: out of resource: shared memory,
#     Required: 106496, Hardware limit: 101376
#
# Le GB10 plafonne a 99 KiB de memoire partagee -- la meme limite que le patch FLA
# amont encode deja (`DEFAULT = 101376  # spark-fla-shmem`). Le noyau en demandait
# 5 120 de trop.
#
# On halve donc le bloc N quand le cache est quantifie, ce que le message d'erreur
# de Triton suggere explicitement. Le cout est un peu de parallelisme par
# programme ; le benefice est que le noyau TIENT. C'est aussi le prix reel du fp8
# sur cette machine, a garder en tete au moment de juger le debit.
ops = remplacer(ops,
    "    num_tiles = triton.cdiv(logical_indices.shape[1], block_n)",
    "    if _kv_mode != 0:\n"
    "        # _cast_kv_tile materialises an fp32 tile, doubling shared memory for\n"
    "        # K and V. sm_121 caps at 101376 bytes and the kernel asked for\n"
    "        # 106496; halving the N block fits.\n"
    "        block_n = max(16, block_n // 2)\n"
    "    num_tiles = triton.cdiv(logical_indices.shape[1], block_n)",
    "bloc N reduit sous quantisation")

ast.parse(ops)
open(OPS, "w").write(ops)
print("ops/qsa.py : noyaux decode + mqa dequantifiants, gardes de dtype leves")

# -------------------------------------------------------------------- qsa.py
owner = open(OWNER).read()

# 10. Ce que le backend DECLARE savoir faire.
owner = remplacer(owner,
    '    supported_kv_cache_dtypes: ClassVar[list[CacheDType]] = ["auto", "bfloat16"]',
    '    supported_kv_cache_dtypes: ClassVar[list[CacheDType]] = [\n'
    '        "auto",\n'
    '        "bfloat16",\n'
    '        "fp8",\n'
    '        "fp8_e4m3",\n'
    '    ]',
    "dtypes declares supportes")

# 11..13. Les trois gardes DECLARATIFS. Ils ne protegeaient rien une fois les
#         noyaux capables ; le seul garde utile etait celui du wrapper (n.5).
owner = remplacer(owner,
    '        if self.kv_cache_dtype not in ("auto", "bfloat16"):\n'
    "            raise NotImplementedError(\n"
    '                "Qwen3.8-Flash-Next QSA requires a BF16 main KV cache"\n'
    "            )",
    '        if self.kv_cache_dtype not in ("auto", "bfloat16", "fp8", "fp8_e4m3"):\n'
    "            raise NotImplementedError(\n"
    '                f"Qwen3.8-Flash-Next QSA: {self.kv_cache_dtype} is not supported "\n'
    '                "(bf16 and fp8_e4m3 are)"\n'
    "            )",
    "garde d'init")

owner = remplacer(owner,
    "        if key_cache.dtype != torch.bfloat16 or query.dtype != torch.bfloat16:\n"
    '            raise NotImplementedError("Qwen3.8-Flash-Next QSA requires BF16 Q/K/V")',
    "        if query.dtype != torch.bfloat16:\n"
    '            raise NotImplementedError("Qwen3.8-Flash-Next QSA requires a BF16 query")\n'
    "        if key_cache.dtype not in (\n"
    "            torch.bfloat16,\n"
    "            torch.float8_e4m3fn,\n"
    "            torch.uint8,\n"
    "        ):\n"
    "            raise NotImplementedError(\n"
    '                f"Qwen3.8-Flash-Next QSA: cache dtype {key_cache.dtype} is not supported"\n'
    "            )",
    "garde d'entree du noyau")

owner = remplacer(owner,
    "        if self.kv_cache_torch_dtype != torch.bfloat16:\n"
    "            raise NotImplementedError(\n"
    '                "Qwen3.8-Flash-Next QSA requires BF16 cache storage"\n'
    "            )",
    "        if self.kv_cache_torch_dtype not in (\n"
    "            torch.bfloat16,\n"
    "            torch.float8_e4m3fn,\n"
    "            # vLLM ALLOCATES the quantised cache as uint8: raw bytes,\n"
    "            # reinterpreted as fp8 right before the kernel (see the\n"
    "            # `.view()` in `forward_qsa`). Rejecting uint8 rejected the\n"
    "            # only storage the core produces.\n"
    "            torch.uint8,\n"
    "        ):\n"
    "            raise NotImplementedError(\n"
    '                f"Qwen3.8-Flash-Next QSA: storage dtype {self.kv_cache_torch_dtype} "\n'
    '                "is not supported"\n'
    "            )",
    "garde de stockage")

# 15. LE GARDE RATE AU PREMIER PASSAGE, et qui a fait echouer le boot.
#
# Ce fichier porte SEPT gardes, pas cinq. Deux vivent dans une AUTRE classe --
# `Qwen3_8FlashNextQSAAttention.__init__` -- et le premier inventaire ne les avait
# pas vus. Celui-ci teste `cache_config.cache_dtype` la ou celui de la l.108 teste
# `self.kv_cache_dtype` : meme message d'erreur, texte different, donc l'assertion
# `count == 1` du patch passait sans rien signaler. Le moteur fp8 est mort au
# demarrage sur ce garde, avec exactement le message que le patch croyait avoir
# leve.
#
# Lecon : chercher les gardes par leur MESSAGE ne suffit pas, il faut les chercher
# par ce qu'ils TESTENT.
owner = remplacer(owner,
    '        if cache_config.cache_dtype not in ("auto", "bfloat16"):\n'
    "            raise NotImplementedError(\n"
    '                "Qwen3.8-Flash-Next QSA requires a BF16 main KV cache"\n'
    "            )",
    '        if cache_config.cache_dtype not in ("auto", "bfloat16", "fp8", "fp8_e4m3"):\n'
    "            raise NotImplementedError(\n"
    '                f"Qwen3.8-Flash-Next QSA: cache_dtype {cache_config.cache_dtype} "\n'
    '                "is not supported (bf16 and fp8_e4m3 are)"\n'
    "            )",
    "garde cache_config.cache_dtype (classe QSAAttention)")

# Le septieme garde -- `quant_config.kv_cache_scheme is not None`, « does not
# support KV quantization » -- vise le schema declare DANS LE CHECKPOINT
# (compressed-tensors), pas `--kv-cache-dtype`. Notre chemin ne le declenche pas ;
# il est laisse en place plutot que leve a l'aveugle.

# 17. LE GARDE DU PARENT, qui teste une capacite dont QSA NE DEPEND PAS.
#
# `Qwen3_8FlashNextQSAImpl` herite de `FlashAttentionImpl` et appelle
# `super().__init__()`. Le parent refuse un cache quantifie
# (`flash_attn.py:918`, « FlashAttention does not support fp8_e4m3 kv-cache on
# this device ») parce que SES noyaux ne savent pas le lire sur SM121.
#
# Mais QSA ne calcule PAS avec les noyaux FlashAttention : il appelle
# `qsa_sparse_paged_attention`, en Triton, et n'herite du parent que pour
# l'infrastructure (metadonnees, plomberie de couche). Le garde est donc hors
# sujet pour lui -- il refuse une capacite qui n'est jamais sollicitee.
#
# On neutralise le dtype LE TEMPS de l'init du parent, puis on le restaure.
# `kv_cache_dtype` est le 7e parametre positionnel, d'ou les deux formes.
owner = remplacer(owner,
    "    def __init__(self, *args, **kwargs) -> None:\n"
    "        super().__init__(*args, **kwargs)\n"
    "        if not is_flash_attn_varlen_func_available():",
    "    def __init__(self, *args, **kwargs) -> None:\n"
    "        # FlashAttentionImpl rejects a quantised cache because ITS kernels\n"
    "        # cannot read it on this device. QSA does not use them: it calls\n"
    "        # qsa_sparse_paged_attention (Triton) and only inherits the\n"
    "        # surrounding plumbing. Neutralise the dtype for the parent init,\n"
    "        # then restore it.\n"
    "        _fp8 = (\"fp8\", \"fp8_e4m3\")\n"
    "        _real_kv_dtype = None\n"
    "        if kwargs.get(\"kv_cache_dtype\") in _fp8:\n"
    "            _real_kv_dtype = kwargs[\"kv_cache_dtype\"]\n"
    "            kwargs[\"kv_cache_dtype\"] = \"auto\"\n"
    "        elif len(args) > 6 and args[6] in _fp8:\n"
    "            _real_kv_dtype = args[6]\n"
    "            args = args[:6] + (\"auto\",) + args[7:]\n"
    "        super().__init__(*args, **kwargs)\n"
    "        if _real_kv_dtype is not None:\n"
    "            self.kv_cache_dtype = _real_kv_dtype\n"
    "        if not is_flash_attn_varlen_func_available():",
    "neutralisation du garde herite de FlashAttentionImpl")

# 16. REINTERPRETATION uint8 -> fp8, juste avant le noyau.
#
# Le cache quantifie est ALLOUE en `torch.uint8` par le cœur. Un `tl.load` sur ce
# pointeur rendrait des ENTIERS, et `_cast_kv_tile` convertirait la valeur entiere
# au lieu de decoder le flottant : des nombres plausibles, totalement faux -- le
# mode de defaillance silencieux qu'on traque depuis le debut.
#
# vLLM resout cela par une REINTERPRETATION DE BITS sans copie, et le fait au meme
# endroit pour l'attention unifiee (`v1/attention/backends/triton_attn.py`) :
#
#     if is_quantized_kv_cache(self.kv_cache_dtype) and key_cache.dtype != fp8:
#         key_cache = key_cache.view(self.fp8_dtype)
#
# On reprend la meme forme, au meme moment : apres la decoupe du cache, avant le
# garde d'entree du noyau.
owner = remplacer(owner,
    "        key_cache = canonicalize_singleton_dim_strides(key_cache)\n"
    "        value_cache = canonicalize_singleton_dim_strides(value_cache)",
    "        key_cache = canonicalize_singleton_dim_strides(key_cache)\n"
    "        value_cache = canonicalize_singleton_dim_strides(value_cache)\n"
    "        # uint8 holds the raw bytes of an fp8 cache: REINTERPRET them, do not\n"
    "        # convert (same step triton_attn.py takes for unified attention).\n"
    "        if key_cache.dtype == torch.uint8:\n"
    "            key_cache = key_cache.view(torch.float8_e4m3fn)\n"
    "            value_cache = value_cache.view(torch.float8_e4m3fn)",
    "reinterpretation uint8 -> fp8")

ast.parse(owner)
open(OWNER, "w").write(owner)
print("qsa.py : fp8_e4m3 declare supporte, gardes declaratifs elargis")
print("dequantisation : `_cast_kv_tile` de vLLM (mode 1 = fp8 per-tensor)")
