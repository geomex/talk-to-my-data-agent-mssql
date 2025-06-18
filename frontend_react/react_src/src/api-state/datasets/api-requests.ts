import { AxiosProgressEvent } from "axios";
import apiClient from "../apiClient";

export type Dataset = {
  id: string;
  name: string;
  created: string;
  size: string;
  file_size?: number;
};

export const getAvailableUseCases = async ({
  signal,
}: {
  signal?: AbortSignal;
}): Promise<string[]> => {
  try {
    // This would typically call a DataRobot API endpoint to get available use cases
    // For now, we'll return an empty array - you can replace this with actual API call
    const { data } = await apiClient.get<string[]>(
      `/v1/registry/use-cases`,
      {
        signal,
      }
    );
    return data;
  } catch (error) {
    console.warn('Could not fetch use cases from DataRobot AI Catalog:', error);
    // Return empty array instead of hardcoded fallbacks
    // This is more honest about what's actually available
    return [];
  }
};

export const getDatasets = async ({
  limit,
  useCases,
  category,
  filterFailed,
  orderBy,
  signal,
}: {
  limit: number;
  useCases?: string[];
  category?: string;
  filterFailed?: boolean;
  orderBy?: string;
  signal?: AbortSignal;
}): Promise<Dataset[]> => {
  // Build query parameters - prioritize use cases as primary filter
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  
  // Primary filter: Use cases (most important)
  if (useCases && useCases.length > 0) {
    params.append('use_cases', useCases.join(','));
  }
  
  // Secondary filters
  if (category) {
    params.append('category', category);
  }
  if (filterFailed !== undefined) {
    params.append('filter_failed', filterFailed.toString());
  }
  if (orderBy) {
    params.append('order_by', orderBy);
  }

  const { data } = await apiClient.get<Dataset[]>(
    `/v1/registry/datasets?${params.toString()}`,
    {
      signal,
    }
  );
  return data;
};

export async function uploadDataset({
  files,
  onUploadProgress,
  catalogIds,
  signal,
}: {
  files?: File[];
  catalogIds?: string[];
  onUploadProgress?: (progressEvent: AxiosProgressEvent) => void;
  signal?: AbortSignal;
}) {
  const formData = new FormData();

  if (files && files.length > 0) {
    files.forEach((file) => formData.append("files", file));
  }

  formData.append("registry_ids", JSON.stringify(catalogIds || []));

  const response = await apiClient.post("/v1/datasets/upload", formData, {
    headers: {
      "content-type": "multipart/form-data",
    },
    onUploadProgress,
    signal,
  });

  const { data } = response;

  return data;
}

export const deleteAllDatasets = async (): Promise<unknown> => {
  const { data } = await apiClient.delete(`/v1/datasets`);

  return data;
};
