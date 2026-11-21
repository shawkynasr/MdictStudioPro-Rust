<script lang="ts">
  let { name }: { name: string } = $props();
  const paths: Record<string,string> = {
    book:'M12 5v15M12 5C9 3 5 3 3 4v15c3-1 6 0 9 1 3-1 6-2 9-1V4c-2-1-6-1-9 1Z',
    box:'m3 7 9-4 9 4v11l-9 4-9-4V7Zm0 0 9 4 9-4M12 11v11M7 5l10 4',
    extract:'M4 10v10h16V10M12 3v11m-4-4 4 4 4-4M4 6h3M17 6h3',
    convert:'M4 7h15l-4-4M20 17H5l4 4M19 7v4M5 17v-4',
    database:'M4 5c0-4 16-4 16 0s-16 4-16 0Zm0 0v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0',
    leaf:'M5 19C1 6 11 5 20 3c-1 10-2 19-15 16Zm0 0L16 8',
    jobs:'M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 7v5l3 2',
    settings:'M4 7h2m4 0h10M4 17h10m4 0h2M10 7a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm8 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
    file:'M13 3H5v18h14V9l-6-6Zm0 0v6h6M8 13h8M8 17h6',
    check:'m5 12 4 4L19 6',
    search:'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm-1 5 5 5',
    folder:'M3 6h7l2 2h9v12H3V6Z',
    back:'m14 6-6 6 6 6',
  };
</script>
<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={paths[name] || paths.book}/></svg>
