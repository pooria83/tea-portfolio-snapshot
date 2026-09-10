"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { FiPhone } from "react-icons/fi";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { PhoneField } from "@/components/input/PhoneField";
import { useLinkPhoneMutation, useVerifyLinkPhoneMutation } from "@/store/api/profileApi";

export function LinkPhoneDialog() {
  const t = useTranslations("profile");
  const errorsT = useTranslations("errors");
  const commonT = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<"phone" | "otp">("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [linkPhone, { isLoading: sending }] = useLinkPhoneMutation();
  const [verifyLinkPhone, { isLoading: verifying }] = useVerifyLinkPhoneMutation();

  const linkPhoneErrorMessages: Record<string, string> = {
    CONFLICT: t("linkPhoneError_CONFLICT"),
    AUTHENTICATION_ERROR: t("linkPhoneError_AUTHENTICATION_ERROR"),
    SERVICE_UNAVAILABLE: t("linkPhoneError_SERVICE_UNAVAILABLE"),
  };

  const getErrorMessage = (err: unknown) => {
    const errorBody = (
      err as {
        data?: {
          error?: { code?: string; message?: string; translation_key?: string | null };
          detail?: string;
        };
      }
    )?.data;
    const code = errorBody?.error?.code || "";
    const translationKey = errorBody?.error?.translation_key;
    return (
      (translationKey && errorsT.has(translationKey) ? errorsT(translationKey) : null) ||
      linkPhoneErrorMessages[code] ||
      errorBody?.error?.message ||
      errorBody?.detail ||
      t("linkPhoneError")
    );
  };

  const handleSendOtp = async () => {
    setError(null);
    try {
      await linkPhone({ phone }).unwrap();
      setStep("otp");
    } catch (error_: unknown) {
      setError(getErrorMessage(error_));
    }
  };

  const handleVerify = async () => {
    setError(null);
    try {
      await verifyLinkPhone({ phone, code: otp }).unwrap();
      toast.success(t("phoneLinked"));
      setOpen(false);
      setStep("phone");
      setPhone("");
      setOtp("");
    } catch (error_: unknown) {
      setError(getErrorMessage(error_));
    }
  };

  const handleOpenChange = (val: boolean) => {
    setOpen(val);
    if (!val) {
      setStep("phone");
      setPhone("");
      setOtp("");
      setError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button type="button" variant="secondary" className="h-10 w-full gap-2 text-base" />
        }
      >
        <FiPhone className="size-4" />
        {t("connectPhone")}
      </DialogTrigger>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{step === "otp" ? t("otp") : t("connectPhone")}</DialogTitle>
          <DialogDescription>
            {step === "otp" ? t("otpSentTo") : t("connectPhoneDesc")}
          </DialogDescription>
        </DialogHeader>

        {step === "phone" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("phone")}</Label>
              <PhoneField
                value={phone}
                onChange={(val) => {
                  setPhone(val);
                  setError(null);
                }}
                placeholder="501234567"
              />
            </div>
            {error && (
              <p className="text-destructive text-sm" role="alert">
                {error}
              </p>
            )}
            <div className="flex gap-2">
              <DialogClose render={<Button type="button" variant="outline" className="flex-1" />}>
                {commonT("cancel")}
              </DialogClose>
              <Button type="button" className="flex-1" disabled={sending} onClick={handleSendOtp}>
                {sending ? t("sending") + "..." : t("sendOtp")}
              </Button>
            </div>
          </div>
        )}

        {step === "otp" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-center text-sm font-medium" dir="ltr">
                {phone}
              </p>
              <div className="flex justify-center py-4" dir="ltr">
                <InputOTP
                  maxLength={6}
                  value={otp}
                  autoComplete="off"
                  pushPasswordManagerStrategy="none"
                  onChange={(val) => {
                    setOtp(val);
                    setError(null);
                  }}
                  aria-invalid={!!error}
                >
                  <InputOTPGroup>
                    <InputOTPSlot index={0} />
                    <InputOTPSlot index={1} />
                    <InputOTPSlot index={2} />
                    <InputOTPSlot index={3} />
                    <InputOTPSlot index={4} />
                    <InputOTPSlot index={5} />
                  </InputOTPGroup>
                </InputOTP>
              </div>
              {error && (
                <p className="text-destructive text-center text-sm" role="alert">
                  {error}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setStep("phone");
                  setError(null);
                }}
              >
                {t("back")}
              </Button>
              <Button
                type="button"
                className="flex-1"
                disabled={verifying || otp.length < 6}
                onClick={handleVerify}
              >
                {verifying ? t("verifying") + "..." : t("verify")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
