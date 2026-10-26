import { Typography } from "antd";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div>
      <Typography.Title level={1}>Page not found</Typography.Title>
      <Typography.Paragraph>That address does not exist.</Typography.Paragraph>
      <Link to="/" className="font-medium text-indigo-800 underline">
        Back to projects
      </Link>
    </div>
  );
}
