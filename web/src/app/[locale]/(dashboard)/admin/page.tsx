"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  HiOutlineCollection,
  HiOutlineClock,
  HiOutlineClipboardList,
  HiOutlineAdjustments,
  HiOutlineChip,
  HiOutlineChatAlt2,
} from "react-icons/hi";
import { FiShield } from "react-icons/fi";
import { DashboardTile } from "@/components/shared/DashboardTile";

export default function AdminDashboardPage() {
  const navT = useTranslations("nav");
  const iconSize = "size-6";

  const tiles = useMemo(
    () => [
      {
        href: "/admin/data",
        icon: <HiOutlineCollection className={iconSize} />,
        label: navT("catalogData"),
        description: navT("catalogDataDescription"),
        className: "bg-gradient-to-br from-blue-600 to-indigo-700",
      },
      {
        href: "/admin/cron",
        icon: <HiOutlineClock className={iconSize} />,
        label: navT("cronJobs"),
        description: navT("cronJobsDescription"),
        className: "bg-gradient-to-br from-amber-500 to-orange-700",
      },
      {
        href: "/admin/settings/llm",
        icon: <FiShield className={iconSize} />,
        label: navT("llmSettings"),
        description: navT("llmSettingsDescription"),
        className: "bg-gradient-to-br from-emerald-500 to-teal-700",
      },
      {
        href: "/admin/settings/prompts",
        icon: <HiOutlineClipboardList className={iconSize} />,
        label: navT("prompts"),
        description: navT("promptsDescription"),
        className: "bg-gradient-to-br from-violet-600 to-purple-800",
      },
      {
        href: "/admin/settings/system",
        icon: <HiOutlineAdjustments className={iconSize} />,
        label: navT("systemSettings"),
        description: navT("systemSettingsDescription"),
        className: "bg-gradient-to-br from-rose-500 to-pink-700",
      },
      {
        href: "/admin/settings/scrapers",
        icon: <HiOutlineChip className={iconSize} />,
        label: navT("scraperHeaders"),
        description: navT("scraperHeadersDescription"),
        className: "bg-gradient-to-br from-slate-600 to-slate-800",
      },
      {
        href: "/admin/chats",
        icon: <HiOutlineChatAlt2 className={iconSize} />,
        label: navT("conversations"),
        description: navT("conversationsDescription"),
        className: "bg-gradient-to-br from-cyan-500 to-blue-700",
      },
    ],
    [navT],
  );

  return (
    <div>
      <h1 className="text-2xl font-bold">{navT("dashboard")}</h1>
      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((tile) => (
          <DashboardTile key={tile.href} {...tile} />
        ))}
      </div>
    </div>
  );
}
