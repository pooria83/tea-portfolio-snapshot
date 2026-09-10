"use client";

import { useEffect, useCallback, useState, Suspense } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useTheme } from "@/components/providers/ThemeProvider";
import { useLoginFlow } from "@/hooks/useLoginFlow";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { setPhone } from "@/store/slices/auth";
import { baseApi } from "@/store/api/baseApi";
import { extractApiError } from "@/lib/api";
import { useRouter } from "@/i18n/routing";
import { PhoneInputSection } from "@/components/input/PhoneInput";
import { OtpInputSection } from "@/components/input/OtpInput";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FiSun, FiMoon } from "react-icons/fi";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";

function LoginContent() {
  const t = useTranslations("auth");
  const appT = useTranslations("app");
  const commonT = useTranslations("common");
  const dispatch = useAppDispatch();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { theme, setTheme } = useTheme();

  const { step, loading, error, sendOtp, verifyOtp, clearError } = useLoginFlow();
  const phone = useAppSelector((s) => s.auth.phone);
  const user = useAppSelector((s) => s.auth.user);

  const [googleError, setGoogleError] = useState<string | null>(() =>
    searchParams.get("google_error") === "1"
      ? decodeURIComponent(searchParams.get("message") ?? "")
      : null,
  );

  const shownError = googleError ?? error;

  const clearAllErrors = useCallback(() => {
    clearError();
    setGoogleError(null);
  }, [clearError]);

  useEffect(() => {
    if (step === "authenticated" && user) {
      const target = user.role === "admin" ? "/admin" : "/seller";
      router.replace(target);
    }
  }, [step, user, router]);

  const handleBack = () => {
    dispatch(setPhone(""));
    clearAllErrors();
  };

  const handleGoogleLogin = useCallback(async () => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) return;
    try {
      const nonce = await dispatch(baseApi.endpoints.googleNonce.initiate()).unwrap();
      const redirectUri = `${globalThis.location.origin}/auth/google/callback`;
      sessionStorage.setItem(`google_oauth_${nonce.state}`, "login");
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        response_type: "code",
        scope: "openid email profile",
        access_type: "offline",
        prompt: "select_account",
        state: nonce.state,
      });
      globalThis.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
    } catch (error) {
      toast.error(extractApiError(error, t("googleLoginFailed")));
    }
  }, [dispatch, t]);

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="relative w-full max-w-sm">
        <div className="absolute end-3 top-3 flex items-center gap-1">
          <LanguageSwitcher align="end" />
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={theme === "dark" ? commonT("themeLight") : commonT("themeDark")}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <FiSun className="size-4" /> : <FiMoon className="size-4" />}
          </Button>
        </div>
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{appT("name")}</CardTitle>
          <CardDescription>{t("login")}</CardDescription>
        </CardHeader>
        <CardContent>
          {step === "phone" && (
            <PhoneInputSection
              onSubmit={sendOtp}
              onGoogleLogin={handleGoogleLogin}
              loading={loading}
              error={shownError}
              onClearError={clearAllErrors}
            />
          )}
          {step === "otp" && (
            <OtpInputSection
              phone={phone}
              onSubmit={verifyOtp}
              onBack={handleBack}
              loading={loading}
              error={shownError}
              onClearError={clearAllErrors}
            />
          )}
        </CardContent>
      </Card>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
