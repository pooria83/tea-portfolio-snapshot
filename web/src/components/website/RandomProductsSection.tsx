"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Swiper, SwiperSlide } from "swiper/react";
import type { Swiper as SwiperClass } from "swiper";
import { A11y, Autoplay, Pagination } from "swiper/modules";
import "swiper/css";
import "swiper/css/pagination";

import { useGetRandomProductsQuery } from "@/store/api/anonymousApi";
import { useCloseOnBack } from "@/hooks/useCloseOnBack";
import { ProductViewDialog } from "@/components/product/ProductViewDialog";
import { HomeProductCard } from "@/components/website/HomeProductCard";
import type { ProductListItem } from "@/types/api";

export function RandomProductsSection() {
  const t = useTranslations("website.products");
  const locale = useLocale();
  const { data: products, isLoading } = useGetRandomProductsQuery({ limit: 20 });
  const [selectedProduct, setSelectedProduct] = useState<ProductListItem | null>(null);
  const swiperRef = useRef<SwiperClass | null>(null);

  const closeProductView = useCallback(() => setSelectedProduct(null), []);

  useCloseOnBack(selectedProduct != null, closeProductView, "home-product-view");

  useEffect(() => {
    const onVisibilityChange = () => {
      const swiper = swiperRef.current;
      if (!swiper) {
        return;
      }
      if (document.hidden) {
        swiper.autoplay.stop();
      } else {
        swiper.autoplay.start();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  if (isLoading) {
    return (
      <section className="mx-auto w-full max-w-6xl px-4 py-10" aria-busy="true">
        <h2 className="mb-4 text-center text-lg font-semibold">{t("title")}</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-5">
          {Array.from({ length: 5 }, (_, index) => (
            <div key={index} className="bg-muted/40 aspect-[4/5] animate-pulse rounded-xl" />
          ))}
        </div>
      </section>
    );
  }

  if (!products || products.length === 0) {
    return null;
  }

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-10">
      <h2 className="mb-4 text-center text-lg font-semibold">{t("title")}</h2>
      <div className="mb-4 flex justify-center">
        <div className="featured-products-pagination flex justify-center" />
      </div>
      <Swiper
        dir={locale === "en" ? "ltr" : "rtl"}
        modules={[A11y, Pagination, Autoplay]}
        spaceBetween={12}
        slidesPerView={1}
        loop
        autoplay={{ delay: 3000, disableOnInteraction: false }}
        pagination={{ el: ".featured-products-pagination", clickable: true }}
        onSwiper={(swiper) => {
          swiperRef.current = swiper;
        }}
        breakpoints={{
          640: { slidesPerView: 3 },
          768: { slidesPerView: 5 },
        }}
        className="!overflow-hidden !px-1 !py-1"
      >
        {products.map((product) => (
          <SwiperSlide key={product.id} className="!h-auto">
            <HomeProductCard product={product} onSelect={setSelectedProduct} />
          </SwiperSlide>
        ))}
      </Swiper>

      <ProductViewDialog
        open={selectedProduct != null}
        storeId={selectedProduct?.store_id ?? ""}
        productId={selectedProduct?.id ?? ""}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedProduct(null);
          }
        }}
      />
    </section>
  );
}
