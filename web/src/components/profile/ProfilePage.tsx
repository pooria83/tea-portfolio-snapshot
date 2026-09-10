"use client";

import { useTranslations, useLocale } from "next-intl";
import { useForm, useWatch, Controller } from "react-hook-form";
import type { UserProfileUpdate } from "@/types/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useState, useCallback } from "react";
import { extractApiError } from "@/lib/api";
import { useSearchParams, usePathname } from "next/navigation";
import { FiAlertTriangle, FiCheckCircle } from "react-icons/fi";
import {
  HiOutlineUser,
  HiOutlinePhone,
  HiOutlineLocationMarker,
  HiOutlineGlobe,
} from "react-icons/hi";
import { FcGoogle } from "react-icons/fc";
import { PageLayout } from "@/components/layout/PageLayout";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { LocationPicker } from "@/components/map/LocationPicker";
import { Skeleton } from "@/components/ui/skeleton";
import { PhotoUploader } from "@/components/upload/PhotoUploader";
import { LinkPhoneDialog } from "@/components/profile/LinkPhoneDialog";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useGetProfileQuery, useUpdateProfileMutation } from "@/store/api/profileApi";
import { useAppDispatch } from "@/store/hooks";
import { baseApi } from "@/store/api/baseApi";

const profileSchema = z.object({
  full_name: z.string().optional(),
  avatar_url: z.string().optional(),
  address: z.string().optional(),
  location: z
    .object({
      lat: z.number(),
      lng: z.number(),
    })
    .nullable()
    .optional(),
  preferred_language: z.string().optional(),
});

const localeNames: Record<string, string> = {
  ar: "العربية",
  en: "English",
  fa: "فارسی",
};

type ProfileFormValues = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const t = useTranslations("common");
  const navT = useTranslations("nav");
  const profT = useTranslations("profile");
  const locale = useLocale();

  const { data: profile, isLoading } = useGetProfileQuery();
  const [updateProfile, { isLoading: saving }] = useUpdateProfileMutation();
  const dispatch = useAppDispatch();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [dismissedAlert, setDismissedAlert] = useState(false);

  let linkResult: "success" | "error" | null = null;
  if (searchParams.get("google_link_success") === "1") {
    linkResult = "success";
  } else if (searchParams.get("google_link_error") === "1") {
    linkResult = "error";
  }
  const showLinkAlert = linkResult !== null && !dismissedAlert;
  const linkAlertType = linkResult || "success";

  const errorCode = searchParams.get("ecode") || "";
  const errorMessages: Record<string, string> = {
    CONFLICT: profT("linkGoogleError_CONFLICT"),
    AUTHENTICATION_ERROR: profT("linkGoogleError_AUTHENTICATION_ERROR"),
    SERVICE_UNAVAILABLE: profT("linkGoogleError_SERVICE_UNAVAILABLE"),
  };
  const linkAlertMessage =
    linkResult === "success"
      ? profT("googleLinked")
      : errorMessages[errorCode] || searchParams.get("message") || profT("linkGoogleError");

  const handleLinkAlertChange = useCallback(
    (open: boolean) => {
      if (!open) {
        setDismissedAlert(true);
        globalThis.history.replaceState(null, "", pathname);
      }
    },
    [pathname],
  );

  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: "",
      avatar_url: "",
      address: "",
      location: null,
      preferred_language: locale,
    },
    ...(profile
      ? {
          values: {
            full_name: profile.full_name || "",
            avatar_url: profile.avatar_url || "",
            address: profile.address || "",
            location:
              profile.location_lat != null && profile.location_lng != null
                ? { lat: profile.location_lat, lng: profile.location_lng }
                : null,
            preferred_language: profile.preferred_language || locale,
          },
        }
      : {}),
  });

  const location = useWatch({ control, name: "location" });
  const avatarUrl = useWatch({ control, name: "avatar_url" });

  const handleGoogleLink = async () => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) return;
    try {
      const nonce = await dispatch(baseApi.endpoints.googleNonce.initiate()).unwrap();
      const redirectUri = `${globalThis.location.origin}/auth/google/callback`;
      sessionStorage.setItem(`google_oauth_${nonce.state}`, "link");
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
      toast.error(extractApiError(error, t("error")));
    }
  };

  const onSubmit = async (data: ProfileFormValues) => {
    try {
      const profileUpdate: UserProfileUpdate = {
        full_name: data.full_name ?? "",
        avatar_url: data.avatar_url ?? "",
        address: data.address ?? "",
        preferred_language: data.preferred_language ?? locale,
      };
      if (data.location) {
        profileUpdate.location_lat = data.location.lat;
        profileUpdate.location_lng = data.location.lng;
      }
      await updateProfile(profileUpdate).unwrap();
      toast.success(profT("saved"));
    } catch (error) {
      toast.error(extractApiError(error, t("error")));
    }
  };

  if (isLoading) {
    return (
      <PageLayout variant="narrow">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          <Skeleton className="h-32 w-32 rounded-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout variant="narrow">
      <h1 className="text-2xl font-bold">{navT("profile")}</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <PhotoUploader
          currentUrl={avatarUrl}
          onUploadComplete={(url: string) => setValue("avatar_url", url)}
          fallback={<HiOutlineUser className="size-5" />}
          label={profT("changeAvatar")}
        />

        <FormField label={profT("fullName")} error={errors.full_name?.message}>
          <InputGroup>
            <InputGroupAddon>
              <HiOutlineUser className="size-4" />
            </InputGroupAddon>
            <InputGroupInput
              {...register("full_name")}
              placeholder={profT("fullNamePlaceholder")}
            />
          </InputGroup>
        </FormField>

        {profile?.phone ? (
          <FormField label={profT("phone")}>
            <InputGroup>
              <InputGroupAddon>
                <HiOutlinePhone className="size-4" />
              </InputGroupAddon>
              <InputGroupInput value={profile.phone} readOnly disabled className="opacity-60" />
            </InputGroup>
          </FormField>
        ) : (
          <FormField label={profT("phone")}>
            <LinkPhoneDialog />
          </FormField>
        )}

        <FormField label={profT("email")}>
          <InputGroup>
            <InputGroupAddon>
              <HiOutlineGlobe className="size-4" />
            </InputGroupAddon>
            <InputGroupInput
              value={profile?.email || ""}
              readOnly
              disabled
              className="opacity-60"
            />
          </InputGroup>
        </FormField>

        {profile && !profile.has_google && (
          <>
            <Separator />
            <div className="space-y-2">
              <p className="text-sm font-medium">{profT("connectGoogleLabel")}</p>
              <p className="text-muted-foreground text-xs">{profT("connectGoogleDesc")}</p>
              <Button
                type="button"
                variant="secondary"
                className="h-10 w-full gap-2 text-base"
                onClick={handleGoogleLink}
              >
                <FcGoogle className="size-5" />
                {profT("connectGoogle")}
              </Button>
            </div>
          </>
        )}

        <FormField label={profT("address")} error={errors.address?.message}>
          <InputGroup>
            <InputGroupAddon>
              <HiOutlineLocationMarker className="size-4" />
            </InputGroupAddon>
            <InputGroupTextarea
              {...register("address")}
              placeholder={profT("addressPlaceholder")}
            />
          </InputGroup>
        </FormField>

        <FormField label={profT("location")}>
          <LocationPicker value={location || null} onChange={(loc) => setValue("location", loc)} />
        </FormField>

        <FormField label={profT("language")}>
          <Controller
            name="preferred_language"
            control={control}
            render={({ field }) => (
              <InputGroup>
                <InputGroupAddon>
                  <HiOutlineGlobe className="size-4" />
                </InputGroupAddon>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="flex-1 rounded-none border-0 bg-transparent px-0 shadow-none ring-0 focus-visible:ring-0">
                    <SelectValue>
                      {(field.value && localeNames[field.value]) || localeNames[locale]}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ar">العربية</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="fa">فارسی</SelectItem>
                  </SelectContent>
                </Select>
              </InputGroup>
            )}
          />
        </FormField>

        <div className="flex justify-end gap-2">
          <Button type="submit" disabled={saving}>
            {saving ? t("loading") : t("save")}
          </Button>
        </div>
      </form>

      <AlertDialog open={showLinkAlert} onOpenChange={handleLinkAlertChange}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogMedia
              className={
                linkAlertType === "error"
                  ? "bg-destructive/10 text-destructive"
                  : "bg-primary/10 text-primary"
              }
            >
              {linkAlertType === "error" ? (
                <FiAlertTriangle className="size-5" />
              ) : (
                <FiCheckCircle className="size-5" />
              )}
            </AlertDialogMedia>
            <AlertDialogTitle>
              {linkAlertType === "error" ? t("error") : profT("googleLinkedTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>{linkAlertMessage}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction
              variant={linkAlertType === "error" ? "destructive" : "default"}
              onClick={() => {
                setDismissedAlert(true);
                globalThis.history.replaceState(null, "", pathname);
              }}
            >
              {t("ok")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageLayout>
  );
}
