import { baseApi } from "./baseApi";

const fileApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    uploadFile: builder.mutation<{ url: string }, { file: File; maxSize?: number }>({
      query: ({ file, maxSize }) => {
        const formData = new FormData();
        formData.append("file", file);
        const params = new URLSearchParams();
        if (maxSize) params.set("max_size", String(maxSize));
        const queryString = params.toString();
        return {
          url: `/files/upload${queryString ? `?${queryString}` : ""}`,
          method: "POST",
          body: formData,
          formData: true,
        };
      },
    }),
  }),
  overrideExisting: true,
});

export const { useUploadFileMutation } = fileApi;
