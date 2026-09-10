"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface OtpInputProps {
  phone: string;
  onSubmit: (otp: string) => void;
  onBack: () => void;
  loading: boolean;
  error: string | null;
  onClearError: () => void;
}

export function OtpInputSection({
  phone,
  onSubmit,
  onBack,
  loading,
  error,
  onClearError,
}: OtpInputProps) {
  const t = useTranslations("auth");
  const [otp, setOtp] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(otp);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="otp">{t("otp")}</Label>
        <p className="text-muted-foreground text-sm">{t("enterOtp")}</p>
        <p className="text-sm font-medium" dir="ltr">
          {phone}
        </p>
        <div className="flex justify-center py-4" dir="ltr">
          <InputOTP
            id="otp"
            maxLength={6}
            value={otp}
            autoFocus
            autoComplete="off"
            pushPasswordManagerStrategy="none"
            onChange={(val) => {
              setOtp(val);
              if (error) onClearError();
            }}
            aria-invalid={!!error}
            aria-describedby={error ? "otp-error" : undefined}
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
          <p id="otp-error" className="text-destructive text-center text-sm" role="alert">
            {error}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Button type="button" variant="outline" className="flex-1" onClick={onBack}>
          {t("back")}
        </Button>
        <Button type="submit" className="flex-1" disabled={loading || otp.length < 6}>
          {loading ? t("verifyOtp") + "..." : t("verifyOtp")}
        </Button>
      </div>
    </form>
  );
}
