from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Sequence

import vapoursynth as vs

from .exprop import ExprOp
from .types import SingleOrArrOpt, StrArr, StrArrOpt, SupportsString
from .util import EXPR_VARS, aka_expr_available, flatten, normalise_planes, to_arr

core = vs.core


def expr_func(
    clips: vs.VideoNode | Sequence[vs.VideoNode], expr: str | Sequence[str],
    format: int | None = None, opt: bool = False, boundary: bool = False
) -> vs.VideoNode:
    args = (clips, expr, format, opt, boundary)
    return core.akarin.Expr(*args) if aka_expr_available else core.std.Expr(*args[:3])


def _combine_norm__ix(ffix: StrArrOpt, n_clips: int) -> List[SupportsString]:
    if ffix is None:
        return [''] * n_clips

    ffix = [ffix] if (type(ffix) in {str, tuple}) else list(ffix)  # type: ignore

    return ffix * max(1, ceil(n_clips / len(ffix)))


def combine(
    clips: Sequence[vs.VideoNode], operator: ExprOp = ExprOp.MAX, suffix: StrArrOpt = None, prefix: StrArrOpt = None,
    expr_suffix: StrArrOpt = None, expr_prefix: StrArrOpt = None, planes: SingleOrArrOpt[int] = None,
    **expr_kwargs: Dict[str, Any]
) -> vs.VideoNode:
    n_clips = len(clips)

    prefixes, suffixes = (_combine_norm__ix(x, n_clips) for x in (prefix, suffix))

    normalized_args = [to_arr(x)[:n_clips + 1] for x in (prefixes, EXPR_VARS, suffixes)]  # type: ignore

    args = zip(*normalized_args)

    operators = operator * (n_clips - 1)

    return expr(clips, [expr_prefix, args, operators, expr_suffix], planes, **expr_kwargs)


def expr(
    clips: Sequence[vs.VideoNode], expr: StrArr, planes: SingleOrArrOpt[int], **expr_kwargs: Dict[str, Any]
) -> vs.VideoNode:
    firstclip = clips[0]
    assert firstclip.format

    n_planes = firstclip.format.num_planes

    expr_array: List[SupportsString] = flatten(expr)  # type: ignore

    expr_array_filtered = filter(lambda x: x is not None and x != '', expr_array)

    expr_string = ' '.join([str(x).strip() for x in expr_array_filtered])

    planesl = normalise_planes(firstclip, planes)

    return expr_func(
        clips, [expr_string if x in planesl else '' for x in range(n_planes)], **expr_kwargs  # type: ignore
    )