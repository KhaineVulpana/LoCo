import React from "react";

type PillProps = {
  label: string;
  tone?: "neutral" | "accent" | "warning";
};

const Pill: React.FC<PillProps> = ({ label, tone = "neutral" }) => {
  return <span className={`pill pill-${tone}`}>{label}</span>;
};

export default Pill;
