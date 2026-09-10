"use client";

import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { sendOtp, verifyOtp, clearError } from "@/store/slices/auth";

export function useLoginFlow() {
  const dispatch = useAppDispatch();
  const { step, loading, error } = useAppSelector((s) => s.auth);

  const handleSendOtp = useCallback(
    (phone: string) => {
      void dispatch(sendOtp(phone));
    },
    [dispatch],
  );

  const handleVerifyOtp = useCallback(
    (otp: string) => {
      void dispatch(verifyOtp(otp));
    },
    [dispatch],
  );

  const handleClearError = useCallback(() => {
    dispatch(clearError());
  }, [dispatch]);

  return {
    step,
    loading,
    error,
    sendOtp: handleSendOtp,
    verifyOtp: handleVerifyOtp,
    clearError: handleClearError,
  };
}
