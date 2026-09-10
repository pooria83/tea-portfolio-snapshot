import { useMemo } from "react";
import { useLocale } from "next-intl";
import { localeValue } from "@/lib/locale";
import {
  useGetProductTypesQuery,
  useGetAttributeGroupsQuery,
  useGetCategoryTreeQuery,
  useGetProductTypeAttributesQuery,
  useGetImageViewTypesQuery,
  useGetBrandsQuery,
  useCreateStoreProductMutation,
  useUpdateStoreProductMutation,
} from "@/store/api/productApi";
import type { AttributeItem, AttributeOptionItem } from "@/types/api";

export function useProductFormData(productTypeId: string) {
  const locale = useLocale();

  const { data: productTypes = [] } = useGetProductTypesQuery();
  const { data: attrGroups = [] } = useGetAttributeGroupsQuery();
  const { data: categoryTree = [] } = useGetCategoryTreeQuery({});
  const { data: allAttributes = [] } = useGetProductTypeAttributesQuery(
    { product_type_id: productTypeId || "none" },
    { skip: !productTypeId },
  );
  const { data: imageViewTypes = [] } = useGetImageViewTypesQuery(productTypeId || "none", {
    skip: !productTypeId,
  });
  const { data: brands = [] } = useGetBrandsQuery();

  const [createProduct, { isLoading: creating }] = useCreateStoreProductMutation();
  const [updateProduct, { isLoading: updating }] = useUpdateStoreProductMutation();

  const groupCodeToId = useMemo(() => {
    const map: Record<string, string> = {};
    for (const g of attrGroups) {
      map[g.code] = g.id;
    }
    return map;
  }, [attrGroups]);

  const groupedAttributes = useMemo(() => {
    const groups: Record<string, AttributeItem[]> = {};
    for (const attr of allAttributes) {
      const g = groups[attr.group_id];
      if (g) {
        g.push(attr);
      } else {
        groups[attr.group_id] = [attr];
      }
    }
    return groups;
  }, [allAttributes]);

  const flatCategories = useMemo(() => {
    const flatten = (nodes: typeof categoryTree, prefix = ""): { id: string; label: string }[] => {
      const result: { id: string; label: string }[] = [];
      for (const node of nodes) {
        const name = localeValue(locale, node.name_ar, node.name_fa, node.name_en);
        const label = prefix ? `${prefix} > ${name}` : name;
        result.push({ id: node.id, label }, ...flatten(node.children || [], label));
      }
      return result;
    };
    return flatten(categoryTree);
  }, [categoryTree, locale]);

  const optionsMap = useMemo(() => {
    const map: Record<string, AttributeOptionItem[]> = {};
    for (const attr of allAttributes) {
      if (attr.options && attr.options.length > 0) {
        map[attr.id] = attr.options;
      }
    }
    return map;
  }, [allAttributes]);

  return {
    productTypes,
    attrGroups,
    categoryTree,
    allAttributes,
    imageViewTypes,
    brands,
    createProduct,
    updateProduct,
    creating,
    updating,
    groupCodeToId,
    groupedAttributes,
    flatCategories,
    optionsMap,
  };
}
