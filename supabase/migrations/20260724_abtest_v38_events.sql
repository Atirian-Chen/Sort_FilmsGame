-- v3.8 experiment instrumentation
-- The v3.3 application emitted experiment_exposed, but the anon insert policy
-- never allowed that event name. Rebuild the allow-list so strict experiment
-- exposures and the four v3.8 feature-interaction events can be stored.

drop policy if exists "analytics events can be inserted by anon" on public.analytics_events;

create policy "analytics events can be inserted by anon"
on public.analytics_events for insert
to anon
with check (
  event_name in (
    'page_view',
    'challenge_opened',
    'ranking_started',
    'ranking_completed',
    'poster_downloaded',
    'share_link_copied',
    'visit',
    'list_opened',
    'list_selected',
    'sorting_started',
    'comparison_made',
    'share_copied',
    'result_viewed',
    'qr_viewed',
    'home_content_rendered',
    'experiment_exposed',
    'heavy_config_viewed',
    'default_start_clicked',
    'sorting_scope_reduced',
    'result_share_prompt_clicked'
  )
);
