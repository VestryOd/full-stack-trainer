import type { MetadataRoute } from 'next';
import { TOPICS } from '@/constants/topics';

const BASE_URL = 'https://full-stack-trainer.netlify.app';

export default function sitemap(): MetadataRoute.Sitemap {
  const topicRoutes = TOPICS.flatMap((topic) => [
    { url: `${BASE_URL}/theory/${topic.id}/`, lastModified: new Date() },
    { url: `${BASE_URL}/questions/${topic.id}/`, lastModified: new Date() },
    { url: `${BASE_URL}/tasks/${topic.id}/`, lastModified: new Date() },
  ]);

  return [
    { url: `${BASE_URL}/`, lastModified: new Date() },
    { url: `${BASE_URL}/theory/`, lastModified: new Date() },
    { url: `${BASE_URL}/questions/`, lastModified: new Date() },
    { url: `${BASE_URL}/quiz/`, lastModified: new Date() },
    { url: `${BASE_URL}/tasks/`, lastModified: new Date() },
    ...topicRoutes,
  ];
}
