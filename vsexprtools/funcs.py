from __future__ import annotations

from functools import partial
from math import ceil
from typing import Any, Iterable, Literal, Sequence, cast

from vstools import (
    CustomRuntimeError, CustomValueError, FuncExceptT, HoldsVideoFormatT, PlanesT, ProcessVariableResClip, StrArr,
    StrArrOpt, StrList, SupportsString, VideoFormatT, VideoNodeIterable, check_variable_format, core, flatten_vnodes,
    get_video_format, to_arr, vs
)

from .exprop import ExprOp, ExprOpBase, ExprList, TupleExprList
from .util import ExprVars, bitdepth_aware_tokenize_expr, complexpr_available, norm_expr_planes

__all__ = [
    'expr_func', 'combine', 'norm_expr',

    'average_merge', 'weighted_merge'
]


def expr_func(
    clips: vs.VideoNode | Sequence[vs.VideoNode], expr: str | Sequence[str],
    format: HoldsVideoFormatT | VideoFormatT | None = None, opt: bool | None = None, boundary: bool = True,
    force_akarin: Literal[False] | FuncExceptT = False, func: FuncExceptT | None = None
) -> vs.VideoNode:
    func = func or force_akarin or expr_func
    clips = list(clips) if isinstance(clips, Sequence) else [clips]
    over_clips = len(clips) > 26

    if not complexpr_available:
        if force_akarin or over_clips:
            raise ExprVars._get_akarin_err('This function only works with akarin plugin!')(func=func)
    elif over_clips and b'src26' not in vs.core.akarin.Version()['expr_features']:  # type: ignore
        raise ExprVars._get_akarin_err('You need at least v0.96 of akarin plugin!')(func=func)

    fmt = None if format is None else get_video_format(format).id

    got_var_res = False

    for clip in clips:
        check_variable_format(clip, func)
        got_var_res = got_var_res or (0 in (clip.width, clip.height))

    if complexpr_available and opt is None:
        opt = all(clip.format.sample_type == vs.INTEGER for clip in clips)  # type: ignore

    if complexpr_available:
        func_impl = partial(core.akarin.Expr, expr=expr, format=fmt, opt=opt, boundary=boundary)
    else:
        func_impl = partial(core.std.Expr, expr=expr, format=fmt)

    if got_var_res:
        if len(clips) == 1:
            return ProcessVariableResClip.from_func(clips[0], func_impl, None, clips[0].format)

        raise CustomValueError('You can run only one var res clip!')

    try:
        return func_impl(clips)
    except Exception:
        raise CustomRuntimeError(
            'There was an error when evaluating the expression:\n' + (
                '' if complexpr_available else 'You might need akarin-plugin, and are missing it.'
            ), func, f'\n{expr}\n'
        )


def _combine_norm__ix(ffix: StrArrOpt, n_clips: int) -> list[SupportsString]:
    if ffix is None:
        return [''] * n_clips

    ffix = [ffix] if isinstance(ffix, (str, tuple)) else list(ffix)  # type: ignore

    return ffix * max(1, ceil(n_clips / len(ffix)))  # type: ignore


def combine(
    clips: VideoNodeIterable, operator: ExprOpBase = ExprOp.MAX, suffix: StrArrOpt = None,
    prefix: StrArrOpt = None, expr_suffix: StrArrOpt = None, expr_prefix: StrArrOpt = None,
    planes: PlanesT = None, split_planes: bool = False, **kwargs: Any
) -> vs.VideoNode:
    clips = flatten_vnodes(clips, split_planes=split_planes)

    n_clips = len(clips)

    prefixes, suffixes = (_combine_norm__ix(x, n_clips) for x in (prefix, suffix))

    args = zip(prefixes, ExprVars(n_clips), suffixes)

    has_op = (n_clips >= operator.n_op) or any(x is not None for x in (suffix, prefix, expr_suffix, expr_prefix))

    operators = operator * max(n_clips - 1, int(has_op))

    return norm_expr(clips, [expr_prefix, args, operators, expr_suffix], planes, **kwargs)


def norm_expr(
    clips: VideoNodeIterable,
    expr: str | StrArr | ExprList | tuple[str | StrArr | ExprList, ...] | TupleExprList,
    planes: PlanesT = None, format: HoldsVideoFormatT | VideoFormatT | None = None,
    opt: bool | None = None, boundary: bool = True,
    force_akarin: Literal[False] | FuncExceptT = False, func: FuncExceptT | None = None,
    split_planes: bool = False,
    **kwargs: Any
) -> vs.VideoNode:
    clips = flatten_vnodes(clips, split_planes=split_planes)

    if isinstance(expr, str):
        nexpr = tuple([[expr]])
    elif isinstance(expr, tuple):
        if isinstance(expr, TupleExprList):
            if len(expr) < 1:
                raise CustomRuntimeError(
                    "When passing a TupleExprList you need at least one expr in it!", func, expr
                )

            nclips: list[vs.VideoNode] | vs.VideoNode = clips

            for e in expr:
                nclips = norm_expr(
                    nclips, e, planes, format, opt, boundary, force_akarin, func, split_planes, **kwargs
                )

            return cast(vs.VideoNode, nclips)
        else:
            nexpr = tuple([to_arr(x) for x in expr])  # type: ignore[arg-type]
    else:
        nexpr = tuple([to_arr(expr)])  # type: ignore[arg-type]

    normalized_exprs = [StrList(plane_expr).to_str() for plane_expr in nexpr]

    normalized_expr = norm_expr_planes(clips[0], normalized_exprs, planes, **kwargs)

    tokenized_expr = [
        bitdepth_aware_tokenize_expr(clips, e, bool(is_chroma))
        for is_chroma, e in enumerate(normalized_expr)
    ]

    return expr_func(clips, tokenized_expr, format, opt, boundary, force_akarin, func)


def average_merge(*clips: VideoNodeIterable) -> vs.VideoNode:
    flat_clips = flatten_vnodes(clips)

    length = len(flat_clips)

    return combine(flat_clips, ExprOp.ADD, zip(((1 / length, ) * length), ExprOp.MUL))


def weighted_merge(*weighted_clips: Iterable[tuple[vs.VideoNode, float]] | tuple[vs.VideoNode, float]) -> vs.VideoNode:
    flat_clips = []

    for clip in weighted_clips:
        if isinstance(clip, tuple):
            flat_clips.append(clip)
        else:
            flat_clips.extend(list(clip))

    clips, weights = zip(*flat_clips)

    return combine(clips, ExprOp.ADD, zip(weights, ExprOp.MUL), expr_suffix=[sum(weights), ExprOp.DIV])
