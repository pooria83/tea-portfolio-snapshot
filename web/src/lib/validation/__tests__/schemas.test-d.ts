import type { z } from "zod";
import type { CategoryOption, StoreListItem, StoreResponse } from "@/types/api";

import { CategoryOptionSchema, StoreListItemSchema, StoreResponseSchema } from "../index";

// Compile-time check: Zod schema output types match TS API types
type SchemaCategoryOption = z.infer<typeof CategoryOptionSchema>;
type SchemaStoreListItem = z.infer<typeof StoreListItemSchema>;
type SchemaStoreResponse = z.infer<typeof StoreResponseSchema>;

// If these fail to compile, the Zod schema and TS type are out of sync
void (null as unknown as SchemaCategoryOption satisfies CategoryOption);
void (null as unknown as SchemaStoreListItem satisfies StoreListItem);
void (null as unknown as SchemaStoreResponse satisfies StoreResponse);
