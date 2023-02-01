from __future__ import annotations

from itertools import cycle
from math import isqrt
from typing import Any, Iterable, Iterator, Literal, SupportsFloat, SupportsIndex

from vstools import (
    ColorRange, ConvMode, CustomEnum, CustomIndexError, FuncExceptT, HoldsVideoFormatT, PlanesT, StrArrOpt, StrList,
    VideoFormatT, VideoNodeIterable, flatten, flatten_vnodes, get_lowest_value, get_neutral_value, get_peak_value,
    split, vs)

from .util import ExprVarRangeT, ExprVars, ExprVarsT, aka_expr_available

__all__ = [
    'ExprOp', 'ExprToken', 'ExprList'
]


class ExprTokenBase(str):
    value: str


class ExprToken(ExprTokenBase, CustomEnum):
    LumaMin = 'ymin'
    ChromaMin = 'cmin'
    Lumamax = 'ymax'
    Chromamax = 'cmax'
    RangeHalf = 'range_half'
    RangeSize = 'range_size'
    RangeMin = 'range_min'
    LumaRangeMin = 'yrange_min'
    ChromaRangeMin = 'crange_min'
    RangeMax = 'range_max'
    LumaRangeMax = 'yrange_max'
    ChromaRangeMax = 'crange_max'
    RangeInMin = 'range_in_min'
    LumaRangeInMin = 'yrange_in_min'
    ChromaRangeInMin = 'crange_in_min'
    RangeInMax = 'range_in_max'
    LumaRangeInMax = 'yrange_in_max'
    ChromaRangeInMax = 'crange_in_max'

    @property
    def is_chroma(self) -> bool:
        return 'chroma' in self._name_.lower()

    def get_value(self, clip: vs.VideoNode, chroma: bool = False, range_in: ColorRange = ColorRange.LIMITED) -> float:
        if self is ExprToken.LumaMin:
            return get_lowest_value(clip, False, ColorRange.LIMITED)

        if self is ExprToken.ChromaMin:
            return get_lowest_value(clip, True, ColorRange.LIMITED)

        if self is ExprToken.Lumamax:
            return get_peak_value(clip, False, ColorRange.LIMITED)

        if self is ExprToken.Chromamax:
            return get_peak_value(clip, True, ColorRange.LIMITED)

        if self is ExprToken.RangeHalf:
            return get_neutral_value(clip, chroma)

        if self is ExprToken.RangeSize:
            return (val := get_peak_value(clip)) + (1 - (val <= 1.0))

        if self is ExprToken.RangeMin:
            return get_lowest_value(clip, chroma)

        if self is ExprToken.LumaRangeMin:
            return get_lowest_value(clip, False)

        if self is ExprToken.ChromaRangeMin:
            return get_lowest_value(clip, True)

        if self is ExprToken.RangeMax:
            return get_peak_value(clip, chroma)

        if self is ExprToken.LumaRangeMax:
            return get_peak_value(clip, False)

        if self is ExprToken.ChromaRangeMax:
            return get_peak_value(clip, True)

        if self is ExprToken.RangeInMin:
            return get_lowest_value(clip, chroma, range_in)

        if self is ExprToken.LumaRangeInMin:
            return get_lowest_value(clip, False, range_in)

        if self is ExprToken.ChromaRangeInMin:
            return get_lowest_value(clip, True, range_in)

        if self is ExprToken.RangeInMax:
            return get_peak_value(clip, chroma, range_in)

        if self is ExprToken.LumaRangeInMax:
            return get_peak_value(clip, False, range_in)

        if self is ExprToken.ChromaRangeInMax:
            return get_peak_value(clip, True, range_in)

    def __getitem__(self, __i: SupportsIndex) -> ExprToken:  # type: ignore
        return ExprTokenBase(f'{self.value}_{ExprVars[__i]}')  # type: ignore


class ExprList(StrList):
    def __call__(
        self, *clips: VideoNodeIterable, planes: PlanesT = None, format: HoldsVideoFormatT | VideoFormatT | None = None,
        opt: bool | None = None, boundary: bool = False, force_akarin: Literal[False] | FuncExceptT = False,
        func: FuncExceptT | None = None, split_planes: bool = False, **kwargs: Any
    ) -> vs.VideoNode:
        from .funcs import norm_expr

        fclips = flatten_vnodes(clips)

        if split_planes:
            fclips = sum(map(split, fclips), list[vs.VideoNode]())

        return norm_expr(fclips, self, planes, format, opt, boundary, force_akarin, func, **kwargs)


class ExprOpBase(str):
    value: str

    def combine(  # type: ignore
        self: ExprOp, *clips: vs.VideoNode | Iterable[vs.VideoNode | Iterable[vs.VideoNode]],
        suffix: StrArrOpt = None, prefix: StrArrOpt = None, expr_suffix: StrArrOpt = None,
        expr_prefix: StrArrOpt = None, planes: PlanesT = None, **expr_kwargs: Any
    ) -> vs.VideoNode:
        from .funcs import combine

        return combine(clips, self, suffix, prefix, expr_suffix, expr_prefix, planes, **expr_kwargs)


class ExprOp(ExprOpBase, CustomEnum):
    # 1 Argument
    EXP = "exp"
    LOG = "log"
    SQRT = "sqrt"
    SIN = "sin"
    COS = "cos"
    ABS = "abs"
    NOT = "not"
    DUP = "dup"
    DUPN = "dupN"
    TRUNC = "trunc"
    ROUND = "round"
    FLOOR = "floor"

    # 2 Arguments
    MAX = "max"
    MIN = "min"
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "pow"
    GT = ">"
    LT = "<"
    EQ = "="
    GTE = ">="
    LTE = "<="
    AND = "and"
    OR = "or"
    XOR = "xor"
    SWAP = "swap"
    SWAPN = "swapN"
    MOD = "%"

    # 3 Arguments
    TERN = "?"
    CLAMP = "clamp"

    # Special Operators
    REL_PIX = '{char:s}[{x:d},{y:d}]'
    ABS_PIX = '{x:d} {y:d} {char:s}[]'

    def __call__(self, *pos_args: Any, **kwargs: Any) -> ExprOpBase:
        args = list[Any](pos_args)

        while True:
            try:
                return ExprOpBase(self.format(*args, **kwargs))
            except KeyError as key:
                try:
                    kwargs.update({str(key)[1:-1]: args.pop(0)})
                except IndexError:
                    raise key

    def __str__(self) -> str:
        return self.value

    def __next__(self) -> ExprOp:
        return self

    def __iter__(self) -> Iterator[ExprOp]:
        return cycle([self])

    def __mul__(self, n: int) -> list[ExprOp]:  # type: ignore[override]
        return [self] * n

    @classmethod
    def clamp(
        cls, min: float | ExprToken = ExprToken.RangeMin, max: float | ExprToken = ExprToken.RangeMax, c: str = ''
    ) -> ExprList:

        if aka_expr_available:
            return ExprList([c, min, max, ExprOp.CLAMP])

        return ExprList([c, min, ExprOp.MAX, max, ExprOp.MAX])

    @classmethod
    def matrix(
        cls, var: str, radius: int, mode: ConvMode = ConvMode.SQUARE, exclude: Iterable[tuple[int, int]] = []
    ) -> ExprList:
        exclude = list(exclude)

        if mode != ConvMode.SQUARE:
            coordinates = [
                (xy, 0) if mode is ConvMode.HORIZONTAL else (0, xy)
                for xy in range(-radius, radius + 1)
            ]
        else:
            coordinates = [
                (x, y)
                for y in range(-radius, radius + 1)
                for x in range(-radius, radius + 1)
            ]

        return ExprList([
            var if x == y == 0 else
            ExprOp.REL_PIX(var, x, y)
            for (x, y) in coordinates
            if (x, y) not in exclude
        ])

    @classmethod
    def convolution(
        cls, var: str, matrix: Iterable[SupportsFloat] | Iterable[Iterable[SupportsFloat]],
        bias: float | None = None, divisor: float | bool = True, saturate: bool = True,
        mode: ConvMode = ConvMode.SQUARE, premultiply: float | int | None = None,
        multiply: float | int | None = None, clamp: bool = False
    ) -> ExprList:
        convolution = list[float](flatten(matrix))  # type: ignore

        conv_len = len(convolution)

        if not conv_len % 2:
            raise ValueError('ExprOp.convolution: convolution length must be odd!')
        elif conv_len < 3:
            raise ValueError('ExprOp.convolution: you must pass at least 3 convolution items!')
        elif mode is ConvMode.SQUARE and conv_len != isqrt(conv_len) ** 2:
            raise ValueError(
                'ExprOp.convolution: with square mode, convolution must represent a square (radius*radius n items)!'
            )

        if mode != ConvMode.SQUARE:
            radius = conv_len // 2
        else:
            radius = isqrt(conv_len) // 2

        rel_pixels = cls.matrix(var, radius, mode)

        output = ExprList([
            rel_pix if weight == 1 else [rel_pix, weight, ExprOp.MUL]
            for rel_pix, weight in zip(rel_pixels, convolution)
            if weight != 0
        ])

        output.extend(ExprOp.ADD * output.mlength)

        if premultiply is not None:
            output.append(premultiply, ExprOp.MUL)

        if divisor is not False:
            if divisor is True:
                divisor = sum(map(float, convolution))

            if divisor not in {0, 1}:
                output.append(divisor, ExprOp.DIV)

        if bias is not None:
            output.append(bias, ExprOp.ADD)

        if not saturate:
            output.append(ExprOp.ABS)

        if multiply is not None:
            output.append(multiply, ExprOp.MUL)

        if clamp:
            output.append(ExprOp.clamp(ExprToken.RangeMin, ExprToken.RangeMax))

        return output

    @staticmethod
    def _parse_planes(
        planesa: ExprVarRangeT, planesb: ExprVarRangeT | None, func: FuncExceptT
    ) -> tuple[ExprVarsT, ExprVarsT]:
        planesa = ExprVars(planesa)

        if planesb is None:
            planesb = ExprVars(planesa.stop, planesa.stop + len(planesa))
        else:
            planesb = ExprVars(planesb)

        if len(planesa) != len(planesb):
            raise CustomIndexError('Both clips must have an equal amount of planes!', func)

        return planesa, planesb

    @classmethod
    def rmse(cls, planesa: ExprVarRangeT, planesb: ExprVarRangeT | None = None) -> ExprList:
        planesa, planesb = cls._parse_planes(planesa, planesb, cls.rmse)

        expr = ExprList()

        for a, b in zip(planesa, planesb):
            expr.append([a, b, cls.SUB, cls.DUP, cls.MUL, cls.SQRT])

        expr.append(cls.MAX * expr.mlength)

        return expr

    @classmethod
    def mae(cls, planesa: ExprVarRangeT, planesb: ExprVarRangeT | None = None) -> ExprList:
        planesa, planesb = cls._parse_planes(planesa, planesb, cls.rmse)
        expr = ExprList()

        for a, b in zip(planesa, planesb):
            expr.append([a, b, cls.SUB, cls.ABS])

        expr.append(cls.MAX * expr.mlength)

        return expr
