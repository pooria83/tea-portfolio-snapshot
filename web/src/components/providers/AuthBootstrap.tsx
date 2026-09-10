"use client";

import { useEffect } from "react";
import { useAppDispatch } from "@/store/hooks";
import { bootstrapAuth } from "@/store/slices/auth";

export function AuthBootstrap() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    void dispatch(bootstrapAuth());
  }, [dispatch]);

  return null;
}
