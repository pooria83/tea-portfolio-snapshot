import { createElement } from "react";
import type { IconType } from "react-icons";
import { FaBlackTie, FaTshirt } from "react-icons/fa";
import { FaPersonHalfDress, FaShoePrints } from "react-icons/fa6";
import { AiFillWallet, AiOutlineSkin } from "react-icons/ai";
import { BiSleepy, BiSwim } from "react-icons/bi";
import { BsFillThreadsFill, BsTextWrap } from "react-icons/bs";
import {
  GiArmoredPants,
  GiBackpack,
  GiBasketballJersey,
  GiBelt,
  GiBoots,
  GiCrown,
  GiDiamondRing,
  GiDress,
  GiEarrings,
  GiGemChain,
  GiGemPendant,
  GiHandBag,
  GiHeadbandKnot,
  GiHighHeel,
  GiKeyring,
  GiLargeDress,
  GiLipstick,
  GiNecklace,
  GiNightSleep,
  GiPerfumeBottle,
  GiRing,
  GiRunningShoe,
  GiSandal,
  GiShirt,
  GiShorts,
  GiShoulderBag,
  GiSkirt,
  GiSleevelessJacket,
  GiSmartphone,
  GiSparkles,
  GiSunglasses,
  GiTie,
  GiTShirt,
  GiTrousers,
  GiUmbrella,
  GiUnderwear,
  GiWatch,
  GiWinterGloves,
  GiWinterHat,
  GiWool,
} from "react-icons/gi";

const iconMap: Record<string, IconType> = {
  AiFillWallet,
  AiOutlineSkin,
  BiSleepy,
  BiSwim,
  BsFillThreadsFill,
  BsTextWrap,
  FaBlackTie,
  FaPersonHalfDress,
  FaShoePrints,
  FaTshirt,
  GiArmoredPants,
  GiBackpack,
  GiBasketballJersey,
  GiBelt,
  GiBoots,
  GiCrown,
  GiDiamondRing,
  GiDress,
  GiEarrings,
  GiGemChain,
  GiGemPendant,
  GiHandBag,
  GiHeadbandKnot,
  GiHighHeel,
  GiKeyring,
  GiLargeDress,
  GiLipstick,
  GiNecklace,
  GiNightSleep,
  GiPerfumeBottle,
  GiRing,
  GiRunningShoe,
  GiSandal,
  GiShirt,
  GiShorts,
  GiShoulderBag,
  GiSkirt,
  GiSleevelessJacket,
  GiSmartphone,
  GiSparkles,
  GiSunglasses,
  GiTie,
  GiTShirt,
  GiTrousers,
  GiUmbrella,
  GiUnderwear,
  GiWatch,
  GiWinterGloves,
  GiWinterHat,
  GiWool,
};

export function getIcon(code: string): IconType | undefined {
  return iconMap[code];
}

export function IconRenderer({
  code,
  className,
  size,
}: {
  code?: string | null;
  className?: string;
  size?: number;
}) {
  if (!code) return null;
  const Icon = getIcon(code);
  if (!Icon) return null;
  const iconProps: Record<string, unknown> = {};
  if (className !== undefined) iconProps.className = className;
  if (size !== undefined) iconProps.size = size;
  return createElement(Icon, iconProps);
}
