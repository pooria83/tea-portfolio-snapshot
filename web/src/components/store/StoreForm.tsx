"use client";

import { useCallback } from "react";
import { useRouter } from "@/i18n/routing";
import { useTranslations, useLocale } from "next-intl";
import { useForm, useWatch, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { extractApiError } from "@/lib/api";
import { HiOutlineShoppingBag, HiOutlineTrash } from "react-icons/hi";
import {
  FiTag,
  FiMapPin,
  FiGlobe,
  FiCamera,
  FiFileText,
  FiLayers,
  FiGrid,
  FiDollarSign,
} from "react-icons/fi";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { LocationPicker } from "@/components/map/LocationPicker";
import { PhotoUploader } from "@/components/upload/PhotoUploader";
import { PhoneField } from "@/components/input/PhoneField";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  useGetCategoriesQuery,
  useGetCountriesQuery,
  useGetCurrenciesQuery,
  useGetStoreTypesQuery,
  useCreateStoreMutation,
  useUpdateStoreMutation,
  useDeleteStoreMutation,
} from "@/store/api/storeApi";
import { getWeekdayNames } from "@/lib/weekdays";
import { storeSchema, type StoreFormValues } from "@/lib/store-schema";
import { WorkingHoursEditor } from "@/components/store/WorkingHoursEditor";
import type { StoreResponse } from "@/types/api";

interface StoreFormProps {
  initialData?: StoreResponse;
  onSuccess?: () => void;
}

export function StoreForm({ initialData, onSuccess }: StoreFormProps) {
  const router = useRouter();
  const t = useTranslations("common");
  const s = useTranslations("store");
  const locale = useLocale();
  const isEdit = !!initialData;
  const weekdays = getWeekdayNames(locale);

  const { data: categories = [], isLoading: loadingCategories } = useGetCategoriesQuery({ locale });
  const { data: storeTypes = [], isLoading: loadingStoreTypes } = useGetStoreTypesQuery({ locale });
  const { data: countries = [], isLoading: loadingCountries } = useGetCountriesQuery({ locale });
  const { data: currencies = [], isLoading: loadingCurrencies } = useGetCurrenciesQuery({ locale });
  const [createStore, { isLoading: creating }] = useCreateStoreMutation();
  const [updateStore, { isLoading: updating }] = useUpdateStoreMutation();
  const [deleteStore, { isLoading: deleting }] = useDeleteStoreMutation();

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors },
  } = useForm<StoreFormValues>({
    resolver: zodResolver(storeSchema),
    defaultValues: initialData
      ? {
          name: initialData.name,
          category_id: initialData.category_id,
          store_type_id: initialData.store_type_id,
          country_code: initialData.country_code,
          price_unit_code: initialData.price_unit_code,
          description: initialData.description || "",
          phone: initialData.phone,
          address: initialData.address,
          location: { lat: initialData.location_lat, lng: initialData.location_lng },
          logo_url: initialData.logo_url || "",
          website: initialData.website || "",
          instagram: initialData.instagram || "",
          working_hours: weekdays.map((d) => {
            const wh = initialData.working_hours.find((h) => h.day_of_week === d.day_of_week);
            return wh
              ? {
                  day_of_week: wh.day_of_week,
                  is_closed: wh.is_closed,
                  open_time: wh.open_time,
                  close_time: wh.close_time,
                }
              : {
                  day_of_week: d.day_of_week,
                  is_closed: false,
                  open_time: "09:00",
                  close_time: "18:00",
                };
          }),
        }
      : {
          name: "",
          category_id: "",
          store_type_id: "",
          country_code: "",
          price_unit_code: "",
          description: "",
          phone: "",
          address: "",
          logo_url: "",
          website: "",
          instagram: "",
          working_hours: weekdays.map((d) => ({
            day_of_week: d.day_of_week,
            is_closed: d.day_of_week === 5,
            open_time: d.day_of_week === 5 ? null : "09:00",
            close_time: d.day_of_week === 5 ? null : "18:00",
          })),
        },
  });

  const logoUrl = useWatch({ control, name: "logo_url" });
  const location = useWatch({ control, name: "location" });

  const onSubmit = async (data: StoreFormValues) => {
    try {
      const payload = {
        name: data.name,
        category_id: data.category_id,
        store_type_id: data.store_type_id,
        country_code: data.country_code,
        price_unit_code: data.price_unit_code,
        phone: data.phone,
        address: data.address,
        location_lat: data.location.lat,
        location_lng: data.location.lng,
        working_hours: data.working_hours.map((wh) => ({
          day_of_week: wh.day_of_week,
          open_time: wh.is_closed ? null : (wh.open_time ?? null),
          close_time: wh.is_closed ? null : (wh.close_time ?? null),
          is_closed: wh.is_closed,
        })),
        ...(data.description ? { description: data.description } : {}),
        ...(data.logo_url ? { logo_url: data.logo_url } : {}),
        ...(data.website ? { website: data.website } : {}),
        ...(data.instagram ? { instagram: data.instagram } : {}),
      };

      if (isEdit && initialData) {
        await updateStore({ id: initialData.id, body: payload }).unwrap();
        toast.success(s("updated"));
      } else {
        await createStore(payload).unwrap();
        toast.success(s("created"));
      }

      if (onSuccess) {
        onSuccess();
      } else {
        router.push("/seller/stores");
      }
    } catch (error) {
      toast.error(extractApiError(error, t("error")));
    }
  };

  const handleDelete = async () => {
    if (!initialData) return;
    try {
      await deleteStore(initialData.id).unwrap();
      toast.success(s("deleted"));
      router.push("/seller/stores");
    } catch (error) {
      toast.error(extractApiError(error, t("error")));
    }
  };

  const handleLogoUpload = useCallback(
    (url: string) => {
      setValue("logo_url", url);
      toast.success(s("logoUploaded"));
    },
    [setValue, s],
  );

  const getError = (field: keyof StoreFormValues) => {
    const msg = errors[field]?.message;
    if (msg === "required") return s("required");
    if (msg === "atLeastOneOpen") return s("atLeastOneOpen");
    return msg;
  };

  const saving = creating || updating;

  if (loadingCategories || loadingStoreTypes || loadingCountries || loadingCurrencies) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  let submitLabel: string;
  if (saving) {
    submitLabel = t("loading");
  } else if (isEdit) {
    submitLabel = s("save");
  } else {
    submitLabel = s("create");
  }

  return (
    <>
      {isEdit && (
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">{s("editTitle")}</h1>
          <AlertDialog>
            <AlertDialogTrigger render={<Button variant="destructive" size="sm" />}>
              <HiOutlineTrash className="size-4" />
              {s("delete")}
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{s("deleteTitle")}</AlertDialogTitle>
                <AlertDialogDescription>{s("deleteDescription")}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{s("cancelDelete")}</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} disabled={deleting} variant="destructive">
                  {deleting ? t("loading") : s("confirmDelete")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <FormField label={s("logo")}>
          <PhotoUploader
            currentUrl={logoUrl}
            onUploadComplete={handleLogoUpload}
            fallback={<HiOutlineShoppingBag className="size-5" />}
            label={isEdit ? s("changeLogo") : s("uploadLogo")}
            maxSize={500}
          />
        </FormField>

        <FormField label={s("name")} error={getError("name")} required>
          <InputGroup>
            <InputGroupAddon align="inline-start">
              <FiTag className="size-4" />
            </InputGroupAddon>
            <InputGroupInput {...register("name")} placeholder={s("namePlaceholder")} />
          </InputGroup>
        </FormField>

        <FormField label={s("category")} error={getError("category_id")} required>
          <Controller
            name="category_id"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="w-full">
                  <FiLayers className="size-4" />
                  <SelectValue placeholder={s("categoryPlaceholder")}>
                    {categories.find((c) => c.id === field.value)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {categories.map((cat) => (
                    <SelectItem key={cat.id} value={cat.id}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        <FormField label={s("storeType")} error={getError("store_type_id")} required>
          <Controller
            name="store_type_id"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="w-full">
                  <FiGrid className="size-4" />
                  <SelectValue placeholder={s("storeTypePlaceholder")}>
                    {storeTypes.find((t) => t.id === field.value)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {storeTypes.map((type) => (
                    <SelectItem key={type.id} value={type.id}>
                      {type.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        <FormField label={s("country")} error={getError("country_code")} required>
          <Controller
            name="country_code"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="w-full">
                  <FiGlobe className="size-4" />
                  <SelectValue placeholder={s("countryPlaceholder")}>
                    {countries.find((c) => c.code === field.value)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {countries.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        <FormField label={s("priceUnit")} error={getError("price_unit_code")} required>
          <Controller
            name="price_unit_code"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value}
                onValueChange={
                  isEdit && (initialData?.active_products_count ?? 0) > 0
                    ? () => toast.error(s("priceUnitChangeBlocked"))
                    : field.onChange
                }
              >
                <SelectTrigger
                  className="w-full"
                  disabled={isEdit && (initialData?.active_products_count ?? 0) > 0}
                >
                  <FiDollarSign className="size-4" />
                  <SelectValue placeholder={s("priceUnitPlaceholder")}>
                    {currencies.find((c) => c.code === field.value)?.symbol}{" "}
                    {currencies.find((c) => c.code === field.value)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {currencies.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.symbol} {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        <FormField label={s("description")} error={getError("description")}>
          <InputGroup>
            <InputGroupAddon align="inline-start">
              <FiFileText className="size-4" />
            </InputGroupAddon>
            <InputGroupTextarea
              {...register("description")}
              placeholder={s("descriptionPlaceholder")}
            />
          </InputGroup>
        </FormField>

        <FormField label={s("phone")} error={getError("phone")} required>
          <Controller
            name="phone"
            control={control}
            render={({ field }) => (
              <PhoneField
                value={field.value}
                onChange={field.onChange}
                placeholder={s("phonePlaceholder")}
              />
            )}
          />
        </FormField>

        <FormField label={s("address")} error={getError("address")} required>
          <InputGroup>
            <InputGroupAddon align="inline-start">
              <FiMapPin className="size-4" />
            </InputGroupAddon>
            <InputGroupInput {...register("address")} placeholder={s("addressPlaceholder")} />
          </InputGroup>
        </FormField>

        <FormField label={s("location")} error={getError("location")}>
          <LocationPicker
            value={location}
            onChange={(loc) => setValue("location", loc, { shouldValidate: true })}
          />
        </FormField>

        <FormField label={s("website")} error={getError("website")}>
          <InputGroup>
            <InputGroupAddon align="inline-start">
              <FiGlobe className="size-4" />
            </InputGroupAddon>
            <InputGroupInput
              type="url"
              dir="ltr"
              {...register("website")}
              placeholder={s("websitePlaceholder")}
              className="text-left"
            />
          </InputGroup>
        </FormField>

        <FormField label={s("instagram")} error={getError("instagram")}>
          <InputGroup>
            <InputGroupAddon align="inline-start">
              <FiCamera className="size-4" />
            </InputGroupAddon>
            <InputGroupInput
              dir="ltr"
              {...register("instagram")}
              placeholder={s("instagramPlaceholder")}
              className="text-left"
            />
          </InputGroup>
        </FormField>

        {errors.working_hours && <p className="text-destructive text-xs">{s("atLeastOneOpen")}</p>}
        <WorkingHoursEditor control={control} locale={locale} />

        <div className="flex justify-end gap-2">
          <Button type="submit" disabled={saving}>
            {submitLabel}
          </Button>
        </div>
      </form>
    </>
  );
}
