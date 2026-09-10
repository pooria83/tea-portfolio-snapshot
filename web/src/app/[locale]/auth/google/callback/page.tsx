"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { googleCodeAuth } from "@/store/slices/auth";
import { useLinkGoogleMutation } from "@/store/api/profileApi";

function GoogleCallbackContent() {
  const t = useTranslations("auth");
  const dispatch = useAppDispatch();
  const router = useRouter();
  const searchParams = useSearchParams();
  const step = useAppSelector((s) => s.auth.step);
  const user = useAppSelector((s) => s.auth.user);
  const calledRef = useRef(false);

  const [linkGoogle] = useLinkGoogleMutation();

  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const oauthFlow = (state && sessionStorage.getItem(`google_oauth_${state}`)) || "login";
  if (state) {
    sessionStorage.removeItem(`google_oauth_${state}`);
  }
  const isLink = oauthFlow === "link";

  useEffect(() => {
    if (!code || calledRef.current) return;
    calledRef.current = true;

    const redirect_uri = `${globalThis.location.origin}/auth/google/callback`;

    if (isLink) {
      const linkArg = state ? { code, redirect_uri, state } : { code, redirect_uri };
      linkGoogle(linkArg)
        .unwrap()
        .then((result) => {
          const target = result.role === "admin" ? "/admin/profile" : "/seller/profile";
          router.replace(`${target}?google_link_success=1`);
        })
        .catch((error: unknown) => {
          const errorBody = (
            error as {
              data?: {
                error?: { code?: string; message?: string; translation_key?: string | null };
                detail?: string;
              };
            }
          )?.data;
          const errorCode = errorBody?.error?.code || "";
          const rawMsg = errorBody?.error?.message || errorBody?.detail || "";
          const translationKey = errorBody?.error?.translation_key || "";
          const target = "/seller/profile";
          router.replace(
            `${target}?google_link_error=1&ecode=${encodeURIComponent(errorCode)}&tkey=${encodeURIComponent(translationKey)}&message=${encodeURIComponent(rawMsg)}`,
          );
        });
    } else {
      const loginArg = state ? { code, redirect_uri, state } : { code, redirect_uri };
      dispatch(googleCodeAuth(loginArg))
        .unwrap()
        .catch((error: unknown) => {
          const message = typeof error === "string" && error.trim() ? error : "google_login_failed";
          router.replace(`/login?google_error=1&message=${encodeURIComponent(message)}`);
        });
    }
  }, [code, isLink, dispatch, router, linkGoogle, state]);

  useEffect(() => {
    if (isLink) return;
    if (!calledRef.current) return;
    if (step !== "authenticated" || !user) return;
    const target = user.role === "admin" ? "/admin" : "/seller";
    router.replace(target);
  }, [step, user, router, isLink]);

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <p className="text-muted-foreground">{t("googleSigningIn")}</p>
    </main>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={null}>
      <GoogleCallbackContent />
    </Suspense>
  );
}
