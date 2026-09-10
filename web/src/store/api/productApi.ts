import { baseApi } from "./baseApi";
import type {
  ProductTypeOption,
  AttributeGroupItem,
  AttributeItem,
  BrandItem,
  CategoryNode,
  GenerateDescriptionResponse,
  ImageViewTypeItem,
  ProductCreate,
  ProductListItem,
  ProductStatsResponse,
  ProductUpdate,
  ProductResponse,
  PaginationMeta,
} from "@/types/api";

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
}

interface PaginatedItems<T> {
  items: T[];
  meta: PaginationMeta;
}

const productApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProductTypes: builder.query<ProductTypeOption[], void>({
      query: () => "/products/types",
      transformResponse: (res: ApiEnvelope<ProductTypeOption[]>) => res.data,
    }),

    getAttributeGroups: builder.query<AttributeGroupItem[], void>({
      query: () => "/products/attribute-groups",
      transformResponse: (res: ApiEnvelope<AttributeGroupItem[]>) => res.data,
    }),

    getCategoryTree: builder.query<CategoryNode[], { product_type_id?: string }>({
      query: ({ product_type_id }) => {
        const params = new URLSearchParams();
        if (product_type_id) params.set("product_type_id", product_type_id);
        return `/products/categories?${params}`;
      },
      transformResponse: (res: ApiEnvelope<CategoryNode[]>) => res.data,
    }),

    getProductTypeAttributes: builder.query<
      AttributeItem[],
      { product_type_id: string; group_id?: string }
    >({
      query: ({ product_type_id, group_id }) => {
        const params = new URLSearchParams({ product_type_id });
        if (group_id) params.set("group_id", group_id);
        return `/products/attributes?${params}`;
      },
      transformResponse: (res: ApiEnvelope<AttributeItem[]>) => res.data,
    }),

    getImageViewTypes: builder.query<ImageViewTypeItem[], string>({
      query: (product_type_id) => `/products/image-view-types?product_type_id=${product_type_id}`,
      transformResponse: (res: ApiEnvelope<ImageViewTypeItem[]>) => res.data,
    }),

    getBrands: builder.query<BrandItem[], void>({
      query: () => "/products/brands",
      transformResponse: (res: ApiEnvelope<BrandItem[]>) => res.data,
    }),

    getMyProductsStats: builder.query<ProductStatsResponse, void>({
      query: () => "/stores/my/products/stats",
      providesTags: ["Product"],
      transformResponse: (res: ApiEnvelope<ProductStatsResponse>) => res.data,
    }),

    getMyProductsPage: builder.query<
      PaginatedItems<ProductListItem>,
      { skip?: number; limit?: number; q?: string; store_id?: string }
    >({
      query: ({ skip = 0, limit = 20, q, store_id }) => {
        const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
        if (q) params.set("q", q);
        if (store_id) params.set("store_id", store_id);
        return `/stores/my/products?${params}`;
      },
      providesTags: ["Product"],
      transformResponse: (res: ApiEnvelope<ProductListItem[]>) => ({
        items: res.data,
        meta: (res.meta ?? {}) as unknown as PaginationMeta,
      }),
    }),

    getStoreProduct: builder.query<ProductResponse, { store_id: string; product_id: string }>({
      query: ({ store_id, product_id }) => `/stores/${store_id}/products/${product_id}`,
      providesTags: (_result, _error, { product_id }) => [{ type: "Product", id: product_id }],
      transformResponse: (res: ApiEnvelope<ProductResponse>) => res.data,
    }),

    createStoreProduct: builder.mutation<
      ProductResponse,
      { store_id: string; data: ProductCreate }
    >({
      query: ({ store_id, data }) => ({
        url: `/stores/${store_id}/products`,
        method: "POST",
        body: data,
      }),
      invalidatesTags: ["Product"],
      transformResponse: (res: ApiEnvelope<ProductResponse>) => res.data,
    }),

    updateStoreProduct: builder.mutation<
      ProductResponse,
      { store_id: string; product_id: string; data: ProductUpdate }
    >({
      query: ({ store_id, product_id, data }) => ({
        url: `/stores/${store_id}/products/${product_id}`,
        method: "PUT",
        body: data,
      }),
      invalidatesTags: (_result, _error, { product_id }) => [
        "Product",
        { type: "Product", id: product_id },
      ],
      transformResponse: (res: ApiEnvelope<ProductResponse>) => res.data,
    }),

    generateProductDescription: builder.mutation<
      GenerateDescriptionResponse,
      { store_id: string; product_id: string; prompt?: string; model?: string }
    >({
      query: ({ store_id, product_id, prompt, model }) => {
        const body: Record<string, string> = {};
        if (prompt) body.prompt = prompt;
        if (model) body.model = model;
        return {
          url: `/stores/${store_id}/products/${product_id}/generate-descriptions`,
          method: "POST",
          body: Object.keys(body).length > 0 ? body : undefined,
        };
      },
      invalidatesTags: ["Product"],
      transformResponse: (res: ApiEnvelope<GenerateDescriptionResponse>) => res.data,
    }),
  }),
  overrideExisting: true,
});

export const {
  useGetProductTypesQuery,
  useGetAttributeGroupsQuery,
  useGetCategoryTreeQuery,
  useGetProductTypeAttributesQuery,
  useGetImageViewTypesQuery,
  useGetBrandsQuery,
  useGetMyProductsStatsQuery,
  useLazyGetMyProductsPageQuery,
  useGetStoreProductQuery,
  useCreateStoreProductMutation,
  useUpdateStoreProductMutation,
  useGenerateProductDescriptionMutation,
} = productApi;
